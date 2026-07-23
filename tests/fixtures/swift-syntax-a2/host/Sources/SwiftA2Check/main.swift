import SwiftA2Core

precondition(checkedInvoice("42") == 2)
precondition(uncheckedInvoice("42") == 2)
precondition(routeInvoice(2) == 8)
print("swift-a2-checks-ok")
