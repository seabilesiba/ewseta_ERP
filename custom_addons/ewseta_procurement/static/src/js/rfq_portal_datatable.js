/** Search, filter, sort, paginate — shared for card + list views */
(function () {
    'use strict';

    function debounce(fn, ms) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function compareValues(a, b, type, dir) {
        let cmp = 0;
        if (type === 'number') {
            cmp = (Number(a) || 0) - (Number(b) || 0);
        } else {
            cmp = String(a || '').localeCompare(String(b || ''), undefined, { sensitivity: 'base' });
        }
        return dir === 'desc' ? -cmp : cmp;
    }

    function itemMatches(el, query, typeFilter) {
        const type = (el.dataset.ewType || '').toLowerCase();
        if (typeFilter && type !== typeFilter) {
            return false;
        }
        if (!query) {
            return true;
        }
        const hay = (el.dataset.ewSearch || '').toLowerCase();
        return hay.indexOf(query) !== -1;
    }

    function sortKey(el, col) {
        const map = {
            title: 'ewTitle',
            reference: 'ewReference',
            type: 'ewTypeSort',
            closing: 'ewClosingTs',
            submissions: 'ewSubmissions',
        };
        const key = map[col];
        if (!key) {
            return '';
        }
        return el.dataset[key] !== undefined ? el.dataset[key] : '';
    }

    class PortalRfqTab {
        constructor(tabRoot) {
            this.tabRoot = tabRoot;
            this.cardsPane = tabRoot.querySelector('.ew-proc-portal__view-pane--cards');
            this.listPane = tabRoot.querySelector('.ew-proc-portal__view-pane--list');
            this.cardsGrid = tabRoot.querySelector('.ew-proc-portal__rfq-grid');
            this.table = tabRoot.querySelector('[data-ew-datatable-table]');
            this.tbody = this.table && this.table.querySelector('tbody');
            this.tableCard = this.table && this.table.closest('.ew-proc-portal__card');
            this.infoEl = tabRoot.querySelector('.ew-proc-portal__filter-info');
            this.paginationEl = tabRoot.querySelector('.ew-proc-portal__filter-pagination');
            this.emptyEl = tabRoot.querySelector('.ew-proc-portal__filter-empty');
            this.searchInput = tabRoot.querySelector('.ew-proc-portal__filter-search');
            this.typeSelect = tabRoot.querySelector('.ew-proc-portal__filter-type');
            this.pageSizeSelect = tabRoot.querySelector('.ew-proc-portal__filter-pagesize');
            this.cards = this.cardsGrid ? Array.from(this.cardsGrid.querySelectorAll('.ew-proc-portal__rfq-card')) : [];
            this.rows = this.tbody ? Array.from(this.tbody.querySelectorAll('tr')) : [];
            this.page = 1;
            this.pageSize = 10;
            this.sortCol = null;
            this.sortDir = 'asc';
            this.query = '';
            this.typeFilter = '';
            this.bind();
            this.apply();
        }

        bind() {
            if (this.searchInput) {
                this.searchInput.addEventListener(
                    'input',
                    debounce(() => {
                        this.query = (this.searchInput.value || '').trim().toLowerCase();
                        this.page = 1;
                        this.apply();
                    }, 200)
                );
            }
            if (this.typeSelect) {
                this.typeSelect.addEventListener('change', () => {
                    this.typeFilter = this.typeSelect.value || '';
                    this.page = 1;
                    this.apply();
                });
            }
            if (this.pageSizeSelect) {
                this.pageSizeSelect.addEventListener('change', () => {
                    this.pageSize = parseInt(this.pageSizeSelect.value, 10) || 10;
                    this.page = 1;
                    this.apply();
                });
            }
            if (this.table) {
                this.table.querySelectorAll('.ew-proc-portal__datatable-th--sortable').forEach((th) => {
                    th.addEventListener('click', () => {
                        const col = th.getAttribute('data-ew-sort');
                        if (!col) {
                            return;
                        }
                        if (this.sortCol === col) {
                            this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
                        } else {
                            this.sortCol = col;
                            this.sortDir = 'asc';
                        }
                        this.updateSortIndicators();
                        this.apply();
                    });
                });
            }
        }

        orderedMatching(items, useSort) {
            let matching = items.filter((el) => itemMatches(el, this.query, this.typeFilter));
            if (useSort && this.sortCol && this.table) {
                const th = this.table.querySelector(`[data-ew-sort="${this.sortCol}"]`);
                const sortType = (th && th.getAttribute('data-ew-sort-type')) || 'text';
                const col = this.sortCol;
                const dir = this.sortDir;
                matching = matching.slice().sort((a, b) =>
                    compareValues(sortKey(a, col), sortKey(b, col), sortType, dir)
                );
            }
            return matching;
        }

        /** Ordered RFQ ids for the current filter (rows drive sort order when set). */
        canonicalIds() {
            const rowMatching = this.orderedMatching(this.rows, true);
            const cardMatching = this.orderedMatching(this.cards, false);
            const source = rowMatching.length ? rowMatching : cardMatching;
            return source.map((el) => el.dataset.ewId).filter(Boolean);
        }

        updateSortIndicators() {
            if (!this.table) {
                return;
            }
            this.table.querySelectorAll('.ew-proc-portal__datatable-th--sortable').forEach((th) => {
                th.classList.remove('ew-proc-portal__datatable-th--asc', 'ew-proc-portal__datatable-th--desc');
                const col = th.getAttribute('data-ew-sort');
                if (col === this.sortCol) {
                    th.classList.add(this.sortDir === 'asc' ? 'ew-proc-portal__datatable-th--asc' : 'ew-proc-portal__datatable-th--desc');
                }
            });
        }

        renderPagination(totalPages) {
            if (!this.paginationEl) {
                return;
            }
            this.paginationEl.innerHTML = '';
            if (totalPages <= 1) {
                return;
            }
            const mkItem = (label, page, disabled, active) => {
                const li = document.createElement('li');
                li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
                const a = document.createElement('button');
                a.type = 'button';
                a.className = 'page-link';
                a.textContent = label;
                if (!disabled && !active) {
                    a.addEventListener('click', () => {
                        this.page = page;
                        this.apply(false);
                    });
                }
                li.appendChild(a);
                return li;
            };
            this.paginationEl.appendChild(mkItem('«', this.page - 1, this.page <= 1, false));
            const maxButtons = 5;
            let start = Math.max(1, this.page - Math.floor(maxButtons / 2));
            let end = Math.min(totalPages, start + maxButtons - 1);
            start = Math.max(1, end - maxButtons + 1);
            for (let p = start; p <= end; p += 1) {
                this.paginationEl.appendChild(mkItem(String(p), p, false, p === this.page));
            }
            this.paginationEl.appendChild(mkItem('»', this.page + 1, this.page >= totalPages, false));
        }

        applyCards(matchingAll, pageIdSet) {
            this.cards.forEach((card) => {
                const id = card.dataset.ewId;
                const visible = matchingAll.has(id) && pageIdSet.has(id);
                card.style.display = visible ? '' : 'none';
            });
            if (this.cardsGrid) {
                this.cardsGrid.classList.toggle('d-none', matchingAll.size === 0);
            }
        }

        applyTable(rowMatching, pageIdSet, reorderDom) {
            if (!this.tbody) {
                return;
            }
            const matchingIds = new Set(rowMatching.map((row) => row.dataset.ewId));
            this.rows.forEach((row) => {
                const id = row.dataset.ewId;
                const visible = matchingIds.has(id) && pageIdSet.has(id);
                row.style.display = visible ? '' : 'none';
            });
            if (reorderDom && this.sortCol) {
                rowMatching.forEach((row) => this.tbody.appendChild(row));
            }
            if (this.tableCard) {
                this.tableCard.classList.toggle('d-none', rowMatching.length === 0);
            }
        }

        apply(reorderDom = true) {
            const ids = this.canonicalIds();
            const matchingAll = new Set(ids);
            const rowMatching = this.orderedMatching(this.rows, true);
            const totalPages = Math.max(1, Math.ceil(ids.length / this.pageSize));
            if (this.page > totalPages) {
                this.page = totalPages;
            }
            const start = (this.page - 1) * this.pageSize;
            const pageIdSet = new Set(ids.slice(start, start + this.pageSize));

            this.applyCards(matchingAll, pageIdSet);
            this.applyTable(rowMatching, pageIdSet, reorderDom);

            const shown = ids.length;
            if (this.infoEl) {
                if (shown === 0) {
                    this.infoEl.textContent = '0 records';
                } else {
                    const from = start + 1;
                    const to = Math.min(start + this.pageSize, shown);
                    this.infoEl.textContent = `Showing ${from}–${to} of ${shown} record${shown === 1 ? '' : 's'}`;
                }
            }
            this.renderPagination(totalPages);
            if (this.emptyEl) {
                this.emptyEl.classList.toggle('d-none', shown > 0);
            }
        }
    }

    function initRfqTabs() {
        document.querySelectorAll('.ew-proc-portal__rfq-tab').forEach((tabRoot) => {
            if (tabRoot._ewPortalRfqTab) {
                tabRoot._ewPortalRfqTab.apply();
                return;
            }
            tabRoot._ewPortalRfqTab = new PortalRfqTab(tabRoot);
        });
    }

    function init() {
        initRfqTabs();
        document.addEventListener('ew-portal-view-changed', initRfqTabs);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
