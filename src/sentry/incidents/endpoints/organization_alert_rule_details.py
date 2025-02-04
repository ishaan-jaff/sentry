from django.db.models import Q
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.base import region_silo_endpoint
from sentry.api.serializers import serialize
from sentry.api.serializers.models.alert_rule import DetailedAlertRuleSerializer
from sentry.incidents.endpoints.bases import OrganizationAlertRuleEndpoint
from sentry.incidents.logic import AlreadyDeletedError, delete_alert_rule
from sentry.incidents.serializers import AlertRuleSerializer as DrfAlertRuleSerializer
from sentry.models import SentryAppComponent, SentryAppInstallation
from sentry.models.rulesnooze import RuleSnooze
from sentry.services.hybrid_cloud.app import app_service
from sentry.services.hybrid_cloud.user.service import user_service


def remove_alert_rule(request: Request, organization, alert_rule):
    try:
        delete_alert_rule(alert_rule, user=request.user, ip_address=request.META.get("REMOTE_ADDR"))
        return Response(status=status.HTTP_204_NO_CONTENT)
    except AlreadyDeletedError:
        return Response("This rule has already been deleted", status=status.HTTP_400_BAD_REQUEST)


@region_silo_endpoint
class OrganizationAlertRuleDetailsEndpoint(OrganizationAlertRuleEndpoint):
    def get(self, request: Request, organization, alert_rule) -> Response:
        """
        Fetch an alert rule.
        ``````````````````
        :auth: required
        """
        # Serialize Alert Rule
        expand = request.GET.getlist("expand", [])
        serialized_rule = serialize(
            alert_rule, request.user, DetailedAlertRuleSerializer(expand=expand)
        )

        # Prepare AlertRuleTriggerActions that are SentryApp components
        errors = []
        for trigger in serialized_rule.get("triggers", []):
            for action in trigger.get("actions", []):
                if action.get("_sentry_app_installation") and action.get("_sentry_app_component"):
                    installation = SentryAppInstallation(
                        **action.get("_sentry_app_installation", {})
                    )
                    component = installation.prepare_ui_component(
                        SentryAppComponent(**action.get("_sentry_app_component")),
                        None,
                        action.get("settings"),
                    )
                    if component is None:
                        errors.append(
                            {
                                "detail": f"Could not fetch details from {installation.sentry_app.name}"
                            }
                        )
                        action["disabled"] = True
                        continue

                    action["formFields"] = component.schema.get("settings", {})

                    # Delete meta fields
                    del action["_sentry_app_installation"]
                    del action["_sentry_app_component"]

        if len(errors):
            serialized_rule["errors"] = errors

        rule_snooze = RuleSnooze.objects.filter(
            Q(user_id=request.user.id) | Q(user_id=None), alert_rule=alert_rule
        ).first()
        if rule_snooze:
            serialized_rule["snooze"] = True
            if request.user.id == rule_snooze.owner_id:
                serialized_rule["snoozeCreatedBy"] = "You"
            else:
                user = user_service.get_user(rule_snooze.owner_id)
                if user:
                    serialized_rule["snoozeCreatedBy"] = user.get_display_name()
            serialized_rule["snoozeForEveryone"] = rule_snooze.user_id is None

        return Response(serialized_rule)

    def put(self, request: Request, organization, alert_rule) -> Response:
        serializer = DrfAlertRuleSerializer(
            context={
                "organization": organization,
                "access": request.access,
                "user": request.user,
                "ip_address": request.META.get("REMOTE_ADDR"),
                "installations": app_service.get_installed_for_organization(
                    organization_id=organization.id
                ),
            },
            instance=alert_rule,
            data=request.data,
        )

        if serializer.is_valid():
            alert_rule = serializer.save()
            return Response(serialize(alert_rule, request.user), status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, organization, alert_rule) -> Response:
        return remove_alert_rule(request, organization, alert_rule)
