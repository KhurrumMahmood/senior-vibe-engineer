function unusedPrivate(): string {
  return "dormant";
}

function directlyUsed(): number {
  return 7;
}

export function publicApi(): number {
  return directlyUsed();
}

export const publicArrow = (): string => "public";

const registryCallback = (): void => undefined;
const eventCallback = (): void => undefined;
const frameworkCallback = (): void => undefined;
const dynamicByName = (): void => undefined;

const registry = { registered: registryCallback };
const emitter = { on(_event: string, _callback: () => void): void {} };
const router = { get(_path: string, _callback: () => void): void {} };
emitter.on("ready", eventCallback);
router.get("/health", frameworkCallback);
const callbackName = "dynamicByName";

void registry;
void callbackName;
