/* global DataTable, $ */

class DBPromotions {
    initialize() {
        console.log("Initializing...")

        this.init_primary_table()
        this.init_values()

        console.log("Correctly initialized.")

        let klass = this

        this.table.on('click', 'tbody td.dt-control', function (e) {
            let tr = e.target.closest('tr');
            let row = klass.table.row(tr);

            if (row.child.isShown()) {
                // This row is already open - close it
                row.child.hide();
            }
            else {
                // Open this row
                row.child(klass.populate_secondary_tables(row.data())).show();

            }
        });
    }

    get_column(name) {
        return $("#users th").filter(function () {
            return $(this).text().trim().toLowerCase() === name.toLowerCase();
        }).index();
    }

    populate_secondary_tables(rowData) {
        var div = $('<div/>')
            .addClass("loading")
            .text("Loading...");

        $.ajax( {
            url: `/users/${rowData[this.get_column("ID")]}/edit_summary`,
            success: function ( response ) {
                div.html( response ).removeClass("loading");
                new DataTable("table#by_year:not(.dataTable)", {
                    paging: false,
                    responsive: true,
                    searching: false,
                    autowidth: false,
                    info: false,
                    order: [[0, 'desc']],
                })
                new DataTable("table#by_tag:not(.dataTable)", {
                    paging: false,
                    responsive: true,
                    searching: false,
                    autowidth: false,
                    info: false,
                    order: [[1, 'desc']],
                })
            },
            error: function(xhr, status, err) {
                console.log("ERROR:", status, err);
            }
        } );

        return div;
    }

    init_primary_table() {
        let klass = this


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
                            klass.get_column("Level"),
                            klass.get_column("Total %")
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
            order: [[klass.get_column("Uploads"), 'desc']],
            columnDefs: [
                {
                    className: "dt-control",
                    orderable: false,
                    data: null,
                    defaultContent: "",
                    targets: 0
                },
                {
                    targets: [klass.get_column("Total %")],
                    searchPanes: {
                        show: true,
                        header: "Additional Filtering",
                        options: [
                            {
                                label: '1. Users For Contrib (<4%, 500 ups, 50 recent)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseFloat(rowData[klass.get_column("recent %")]) < 4
                                        && parseInt(rowData[klass.get_column("uploads")]) > 500
                                        && parseInt($(rowData[klass.get_column("recent uploads")]).text()) > 50;
                                }
                            },
                            {
                                label: '2. Translators for Builder (>2000 notes)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt($(rowData[klass.get_column("notes")]).text()) > 2000 && rowData[klass.get_column("level")].display !== "Builder";
                                }
                            },
                            {
                                label: '3. Gardeners for Builder (>5000 edits)',
                                // eslint-disable-next-line no-unused-vars
                                value: function (rowData, rowIdx) {
                                    return parseInt($(rowData[klass.get_column("edits")]).text()) > 5000 && rowData[klass.get_column("level")].display !== "Builder";
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
