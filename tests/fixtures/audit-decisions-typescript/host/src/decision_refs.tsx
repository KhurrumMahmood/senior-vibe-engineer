export function DecisionPanel() {
  return (
    <section>
      {/* decision:0001 */}
      <p>// decision:9006</p>
      <p>{"/* decision:9007 */"}</p>
    </section>
  );
}

const fragment = <>{/* decision:0001 */}<p>// decision:9441</p><p>/* decision:9442 */</p></>;
const quotedCommaAttribute = <p data-label="a,b">/* decision:9443 */</p>;

const genericWithComma = <T,>(value: T) => {
  /* decision:0002 */
  return value;
};
const genericWithConstraint = <T extends unknown>(value: T) => {
  // decision:0003
  return value;
};

const genericSelfClosing = <Select<number> />; /* decision:0002 */
const nestedGenericSelfClosing = <Select<Map<string, number>> data-label="a,b>c" />; // decision:0003
const memberGenericSelfClosing = <UI.Select<Result<string>, Error> />; /** decision:0001 */
const functionGenericSelfClosing = <Select<(value: string) => number> />; // decision:0003
const genericElement = <Select<number>>/* decision:9450 */</Select>; // decision:0002

export {
  fragment,
  functionGenericSelfClosing,
  genericElement,
  genericSelfClosing,
  genericWithComma,
  genericWithConstraint,
  memberGenericSelfClosing,
  nestedGenericSelfClosing,
  quotedCommaAttribute,
};
