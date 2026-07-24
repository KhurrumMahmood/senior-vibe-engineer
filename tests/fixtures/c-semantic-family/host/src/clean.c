typedef enum stable_state {
    STABLE_STATE_READY = 0
} stable_state;

int stable_identity(int value)
{
    return value + STABLE_STATE_READY;
}
