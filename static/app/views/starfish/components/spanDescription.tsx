import styled from '@emotion/styled';

import {CodeSnippet} from 'sentry/components/codeSnippet';
import {SpanMetricsFields, SpanMetricsFieldTypes} from 'sentry/views/starfish/types';
import {SQLishFormatter} from 'sentry/views/starfish/utils/sqlish/SQLishFormatter';

type Props = {
  span: Pick<
    SpanMetricsFieldTypes,
    SpanMetricsFields.SPAN_OP | SpanMetricsFields.SPAN_DESCRIPTION
  >;
};

export function SpanDescription({span}: Props) {
  if (span[SpanMetricsFields.SPAN_OP].startsWith('db')) {
    return <DatabaseSpanDescription span={span} />;
  }

  return <WordBreak>{span[SpanMetricsFields.SPAN_DESCRIPTION]}</WordBreak>;
}

function DatabaseSpanDescription({span}: Props) {
  const formatter = new SQLishFormatter();

  return (
    <CodeSnippet language="sql">
      {formatter.toString(span[SpanMetricsFields.SPAN_DESCRIPTION])}
    </CodeSnippet>
  );
}

const WordBreak = styled('div')`
  word-break: break-word;
`;
