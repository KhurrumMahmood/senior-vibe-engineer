export function generatedOne(input: string): { value: string; status: string } {
  return { value: input.trim(), status: "generated" };
}

export function generatedTwo(input: string): { value: string; status: string } {
  return { value: input.trim(), status: "generated" };
}
