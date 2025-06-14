/* global DataTable */

class DBPromotions {
    initialize() {
        console.log("Initializing...")

        this.init_table()
        this.init_values()

        console.log("Correctly initialized.")
    }

    init_table() {
        this.table = new DataTable("table#users", {
            paging: false,
            responsive: true,
            layout: {
                topEnd: null
            },
            fixedHeader: {
                header: true,
                footer: true
            },
            saveState: true,
            order: [[5, 'desc']],
            // initComplete: function () {
            //     this.api().columns().every(function () {
            //         let column = this;
            //         let title = column.footer().textContent;
            //         if (!title) {
            //             return
            //         }

            //         // Create input element
            //         let input = document.createElement("input");
            //         input.placeholder = title;
            //         column.footer().replaceChildren(input);

            //         // Event listener for user input
            //         let range_columns = ["Level", "Uploads", "Recent Uploads", "Recent Deleted", "Recent %", "Notes", "Edits"]

            //         input.addEventListener("keyup", () => {
            //             if (column.search() !== input.value) {
            //                 if (range_columns.includes(title)) {
            //                     console.log(title)
            //                 }
            //                 column.search(input.value).draw();
            //             }
            //         });
            //     });
            // }
        });
    }

    init_values() {
        this.max_ratio_for_contrib = parseInt(document.querySelector("meta[name='contrib_max_del_perc']").content)
        this.max_ratio_for_builder = parseInt(document.querySelector("meta[name='builder_max_del_perc']").content)
        this.max_deleted_bad = parseInt(document.querySelector("meta[name='max_deleted_bad']").content)
        this.max_deleted_warning = parseInt(document.querySelector("meta[name='max_deleted_warning']").content)
    }
}

window.DBPromotions = new DBPromotions();
