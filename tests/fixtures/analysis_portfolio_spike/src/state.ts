import { normalize } from "./util";

export enum Status {
  Draft = "draft",
  Published = "published",
}

export interface Item {
  status: Status;
  count: number;
}

export const initial: Item = { status: Status.Draft, count: 0 };

export function transition(item: Item, next: Status): Item {
  const normalized = normalize(next);
  if (item.status === normalized) {
    return item;
  }
  item.status = normalized;
  return { ...item, status: normalized };
}

export function dispatch(item: Item): Item {
  return transition(item, Status.Published);
}
