/* global Tablesort */

class DBPromotions {
    initialize() {
        // let tables be sortable
        console.log("Initializing...")

        this.init_tablesort()

        this.max_ratio_for_contrib = parseInt(document.querySelector("meta[name='contrib_max_del_perc']").content)
        this.max_ratio_for_builder = parseInt(document.querySelector("meta[name='builder_max_del_perc']").content)
        this.max_deleted_bad = parseInt(document.querySelector("meta[name='max_deleted_bad']").content)
        this.max_deleted_warning = parseInt(document.querySelector("meta[name='max_deleted_warning']").content)

        console.log("Correctly initialized.")
    }

    init_tablesort() {
        new Tablesort(document.querySelector('table#contrib-builder'))
         new Tablesort(document.querySelector('table#contrib-member'))
        new Tablesort(document.querySelector('table#builder'))

    }
}

window.DBPromotions = new DBPromotions();
