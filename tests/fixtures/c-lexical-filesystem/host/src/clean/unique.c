int unique_checksum(int left, int right)
{
    int mixed = (left * 31) + right;
    return mixed ^ (mixed >> 2);
}
