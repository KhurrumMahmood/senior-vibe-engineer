package example.thirdparty;

public final class VendorOnly {
    public String status;

    public boolean vendorOnly() {
        return status.equals("vendor");
    }
}
