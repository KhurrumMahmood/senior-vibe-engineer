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

export { fragment, genericWithComma, genericWithConstraint, quotedCommaAttribute };
