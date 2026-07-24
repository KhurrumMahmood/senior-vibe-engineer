package cohort

fun loadPayments() = 1
fun savePayments() = 2
fun loadCustomers() = 3
fun saveCustomers() = 4
fun loadExports() = 5
fun saveExports() = 6
fun renderExports(): Int = loadExports() + saveExports()
fun loadNotifications() = 7
fun saveNotifications() = 8
