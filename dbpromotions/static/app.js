/* global DataTable, $ */

class DBPromotions {
    initialize() {
        console.log("Initializing...")

        this.init_table()
        this.init_values()


        console.log("Correctly initialized.")
    }

    column_index_from_name(name) {
        return $("#users th").filter(function () {
            return $(this).text().trim().toLowerCase() === name.toLowerCase();
        }).index();
    }

    init_table() {
        this.table = new DataTable("table#users", {
            initComplete: function() { $("table#users").show(); },
            paging: true,
            lengthMenu: [10, 25, 50, 75, 100, 1000],
            pageLength: 25,
            responsive: true,
            layout: {
                top3: {
                    searchPanes: {
                        columns: [ // Specifies which columns to include in the search panes
                            this.column_index_from_name("Level"),
                            this.column_index_from_name("Total %")
                        ],
                        controls: false,
                        dtOpts: {
                            select: {
                                style: 'multi'
                            }
                        }
                    }
                },
                top2Start: 'pageLength',
                top2End: 'search',
                topStart: 'info',
                topEnd: 'paging',
                bottomStart: 'pageLength',
                bottomEnd: 'search',
                bottom2Start: 'info',
                bottom2End: 'paging'
            },
            fixedHeader: {
                header: true,
                footer: true,
            },
            searchPanes: {
                viewTotal: true
            },
            stateSave: true,
            order: [[this.column_index_from_name("Uploads"), 'desc']],
            columnDefs: [
                {
                    targets: [this.column_index_from_name("Total %")],
                    searchPanes: {
                        show: true,
                        header: "Additional Filtering",
                        options: [
                            {
                                label: '1. Users For Contrib (<4%, 500 ups, 50 recent)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseFloat(rowData[9]) < 4 && parseInt(rowData[4]) > 500 && parseInt($(rowData[7]).text()) > 50;
                                }
                            },
                            {
                                label: '2. Translators for Builder (>2000 notes)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt($(rowData[10]).text()) > 2000 && rowData[1].display !== "Builder";
                                }
                            },
                            {
                                label: '3. Gardeners for Builder (>5000 edits)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt($(rowData[11]).text()) > 5000 && rowData[1].display !== "Builder";
                                }
                            },
                        ]
                    },
                },
            ],
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
