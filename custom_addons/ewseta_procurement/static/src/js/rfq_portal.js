odoo.define('ewseta_procurement.rfq_portal', function (require) {
  'use strict';

  const rpc = require('web.rpc');

  async function getSessionInfo() {
    // to get csrf token for POST
    return await rpc.query({route: '/web/session/get_session_info', params: {}});
  }

  async function fetchRFQs() {
    return await rpc.query({route: '/procurement/api/rfqs', params: {}});
  }

  async function fetchRFQDetail(id) {
    return await rpc.query({route: `/procurement/api/rfq/${id}`, params: {}});
  }

  function h(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'class') el.className = v; else el.setAttribute(k, v);
    });
    (Array.isArray(children) ? children : [children]).forEach(c => {
      if (c == null) return;
      el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return el;
  }

  async function mount() {
    const root = document.getElementById('ew-rfq-app');
    if (!root) return;

    root.innerHTML = '';
    root.appendChild(h('h1', {}, ['Open RFQs/RFPs']));
    const listWrap = h('div', {class: 'rfq-list'}, []);
    root.appendChild(listWrap);

    const { rfqs } = await fetchRFQs();
    if (!rfqs || !rfqs.length) {
      listWrap.appendChild(h('div', {class: 'alert alert-info'}, ['No open RFQs at the moment.']));
      return;
    }

    const table = h('table', {class: 'table table-striped align-middle'}, [
      h('thead', {}, [
        h('tr', {}, ['Title','Reference','Type','Closing',''].map(t => h('th', {}, [t])))
      ]),
      h('tbody')
    ]);
    listWrap.appendChild(table);
    const tbody = table.querySelector('tbody');

    rfqs.forEach(r => {
      const btn = h('button', {class: 'btn btn-primary btn-sm'}, ['Apply']);
      btn.addEventListener('click', () => renderApplyForm(root, r.id));
      const tr = h('tr', {}, [
        h('td', {}, [r.name]),
        h('td', {}, [r.reference || '']),
        h('td', {}, [r.type.toUpperCase()]),
        h('td', {}, [r.closing_at || '']),
        h('td', {style: 'text-align:right;'}, [btn]),
      ]);
      tbody.appendChild(tr);
    });
  }

  async function renderApplyForm(root, rfqId) {
    const detail = await fetchRFQDetail(rfqId);
    if (detail.error) {
      alert('This RFQ is closed or unavailable.');
      return mount();
    }
    const formWrap = h('div', {class: 'apply-form'}, []);
    formWrap.appendChild(h('h2', {}, [detail.name]));
    formWrap.appendChild(h('p', {class: 'text-muted'}, [`Ref: ${detail.reference || '-'} · Closing: ${detail.closing_at || ''}`]));

    const form = h('form', {class: 'o_website_form'});
    const row = h('div', {class: 'row g-3'});
    form.appendChild(row);

    row.appendChild(makeInput('Company Name *', {name: 'company_name', required: 'required'}));
    row.appendChild(makeInput('Contact Name', {name: 'contact_name'}));
    row.appendChild(makeInput('Contact Email *', {name: 'contact_email', type: 'email', required: 'required'}));

    const mandTitle = h('h5', {}, ['Mandatory Documents']);
    form.appendChild(mandTitle);
    const mandRow = h('div', {class: 'row g-3'});
    form.appendChild(mandRow);

    const opt = [];
    (detail.requirements || []).forEach(req => {
      const col = h('div', {class: 'col-md-6'});
      const lbl = h('label', {class: 'form-label'}, [req.name, req.mandatory ? ' *' : '', req.help ? ` – ${req.help}` : '']);
      const inp = h('input', {type: 'file', name: `file_req_${req.id}`, class: 'form-control'});
      if (req.mandatory) inp.setAttribute('required', 'required');
      col.appendChild(lbl);
      col.appendChild(inp);
      if (req.mandatory) mandRow.appendChild(col); else opt.push(col);
    });

    if (opt.length) {
      form.appendChild(h('h5', {class: 'mt-4'}, ['Optional Documents']));
      const optRow = h('div', {class: 'row g-3'});
      opt.forEach(c => optRow.appendChild(c));
      form.appendChild(optRow);
    }

    const btnRow = h('div', {class: 'mt-4 d-flex gap-2'}, []);
    const submitBtn = h('button', {type: 'submit', class: 'btn btn-primary'}, ['Submit Application']);
    const backBtn = h('button', {type: 'button', class: 'btn btn-outline-secondary'}, ['Back']);
    backBtn.addEventListener('click', () => mount());
    btnRow.appendChild(submitBtn);
    btnRow.appendChild(backBtn);
    form.appendChild(btnRow);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const session = await getSessionInfo();
      const fd = new FormData(form);
      fd.append('rfq_id', String(rfqId));
      // include csrf for public POST
      fd.append('csrf_token', session.csrf_token || '');

      const res = await fetch('/procurement/api/submit', {
        method: 'POST',
        body: fd,
      });
      if (res.ok) {
        root.innerHTML = '';
        root.appendChild(h('div', {class: 'alert alert-success'}, ['Thank you! Your application has been submitted.']));
        const back = h('button', {class: 'btn btn-secondary mt-3'}, ['Back to RFQs']);
        back.addEventListener('click', () => mount());
        root.appendChild(back);
      } else {
        alert(await res.text());
      }
    });

    // replace list with form
    root.innerHTML = '';
    root.appendChild(formWrap);
    formWrap.appendChild(form);
  }

  function makeInput(label, attrs) {
    const col = document.createElement('div');
    col.className = 'col-md-6';
    col.appendChild(h('label', {class: 'form-label'}, [label]));
    col.appendChild(h('input', Object.assign({type: 'text', class: 'form-control'}, attrs || {})));
    return col;
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('ew-rfq-app')) {
      mount();
    }
  });
});
