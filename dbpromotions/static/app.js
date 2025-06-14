/* global DataTable, $ */

class DBPromotions {
    initialize() {
        console.log("Initializing...")

        this.init_table()
        this.init_values()

        console.log("Correctly initialized.")
    }

    init_table() {
        this.table = new DataTable("table#users", {
            columnDefs: [
                {
                    targets: [6],
                    searchPanes: {
                        show: true,
                        header: "Additional Filtering",
                        options: [
                            {
                                label: '1. For Contrib (<4%, 50 recent)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseFloat(rowData[8]) < 4 && parseInt(rowData[3]) > 500 && parseInt($(rowData[6]).text()) > 50;
                                }
                            },
                            {
                                label: '2. Translators for Builder (>2000 notes)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt(rowData[9]) > 2000 && rowData[1].display !== "Builder";
                                }
                            },
                            {
                                label: '3. Editors for Builder (>5000 edits)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt($(rowData[10]).text()) > 5000 && rowData[1].display !== "Builder";
                                }
                            },
                        ]
                    },
                },
            ],
            paging: false,
            responsive: true,
                layout: {
                    top1: {
                        info: {
                            text: 'Showing _TOTAL_ users'
                        }
                    },
                    top2: {
                        searchPanes: {
                            columns: [1, 6],  // Specifies which columns to include in the search panes
                            controls: false,
                            dtOpts: {
                                select: {
                                    style: 'multi'
                                }
                            }
                        }
                    },
                    topStart: null,
                    topEnd: null,
                    bottomStart: null,
                    bottomEnd: null,
            },
            fixedHeader: {
                header: true,
                footer: true
            },
            searchPanes: {
                layout: "columns-1",
            },
            stateSave: true,
            order: [[3, 'desc']],
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
