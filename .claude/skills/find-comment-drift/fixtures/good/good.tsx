interface UserCardProps {
    name: string;
}

export function UserCard(props: UserCardProps) {
    return <section>{props.name}</section>;
}
