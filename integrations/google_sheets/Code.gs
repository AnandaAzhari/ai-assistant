/* Taqi AI Assistant - Google Sheets mirror receiver
 * Pasang sebagai bound Apps Script pada spreadsheet Finance Dashboard.
 * Secret disimpan di Script Properties dengan key SYNC_SECRET.
 */

function doPost(e) {
  try {
    const payload = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const expected = PropertiesService.getScriptProperties().getProperty('SYNC_SECRET');
    if (!expected) return json_({ok:false,error:'SYNC_SECRET belum diatur di Script Properties.'});
    if (!payload.secret || payload.secret !== expected) return json_({ok:false,error:'Secret tidak cocok.'});

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const txCount = syncTransactions_(ss, payload.transactions || []);
    const accountCount = syncAccounts_(ss, payload.accounts || []);
    const categoryCount = syncCategories_(ss, payload.categories || []);
    return json_({ok:true,transactions:txCount,accounts:accountCount,categories:categoryCount});
  } catch (err) {
    return json_({ok:false,error:String(err && err.message ? err.message : err)});
  }
}

function syncTransactions_(ss, rows) {
  const sheet = ss.getSheetByName('Transaksi');
  if (!sheet) throw new Error('Sheet Transaksi tidak ditemukan.');
  const ids = {};
  const last = sheet.getLastRow();
  if (last >= 2) {
    sheet.getRange(2,1,last-1,1).getValues().forEach((r,i) => {
      if (r[0]) ids[String(r[0])] = i + 2;
    });
  }
  let count = 0;
  rows.forEach(item => {
    const values = [[
      item.id || '',
      item.date || '',
      item.time || '',
      item.kind === 'income' ? 'Pemasukan' : 'Pengeluaran',
      item.business || '',
      item.category || '',
      item.description || '',
      item.account || '',
      Number(item.amount || 0),
      item.status || 'confirmed',
      item.source || '',
      '',
      '',
      'Finance Agent',
      item.timestamp || '',
      '',
      '',
      '',
      'synced',
      item.source_event_id || item.id || '',
      new Date()
    ]];
    const row = ids[String(item.id)] || sheet.getLastRow() + 1;
    sheet.getRange(row,1,1,21).setValues(values);
    if (!ids[String(item.id)]) ids[String(item.id)] = row;
    count++;
  });
  return count;
}

function accountMeta_(name) {
  const map = {
    'Cash':['Cash','Tunai','Uang tunai fisik'],
    'BCA':['Bank','BCA','Rekening bank'],
    'BNI':['Bank','BNI','Rekening bank'],
    'SeaBank':['Bank','SeaBank','Rekening bank'],
    'Jago':['Bank','Bank Jago','Rekening bank'],
    'QRIS':['Digital','QRIS','Penerimaan pembayaran QRIS'],
    'DANA':['E-wallet','DANA','Dompet digital'],
    'GoPay':['E-wallet','GoPay','Dompet digital'],
    'ShopeePay':['E-wallet','ShopeePay','Dompet digital']
  };
  return map[name] || ['Lainnya',name,''];
}

function syncAccounts_(ss, rows) {
  const sheet = ss.getSheetByName('Akun');
  if (!sheet) throw new Error('Sheet Akun tidak ditemukan.');
  const index = {};
  const last = sheet.getLastRow();
  if (last >= 2) {
    sheet.getRange(2,1,last-1,1).getValues().forEach((r,i) => {
      if (r[0]) index[String(r[0])] = i + 2;
    });
  }
  let count = 0;
  rows.forEach(item => {
    const meta = accountMeta_(item.name);
    const values = [[
      item.name,
      meta[0],
      meta[1],
      Number(item.opening_balance || 0),
      'Ya',
      meta[2],
      Number(item.balance || 0),
      new Date()
    ]];
    const row = index[String(item.name)] || sheet.getLastRow() + 1;
    sheet.getRange(row,1,1,8).setValues(values);
    if (!index[String(item.name)]) index[String(item.name)] = row;
    count++;
  });
  return count;
}

function syncCategories_(ss, rows) {
  const sheet = ss.getSheetByName('Kategori');
  if (!sheet) throw new Error('Sheet Kategori tidak ditemukan.');
  const index = {};
  const last = sheet.getLastRow();
  if (last >= 2) {
    sheet.getRange(2,1,last-1,2).getValues().forEach((r,i) => {
      if (r[0] && r[1]) index[String(r[0]) + '|' + String(r[1])] = i + 2;
    });
  }
  let count = 0;
  rows.forEach(item => {
    const jenis = item.kind === 'income' ? 'Pemasukan' : 'Pengeluaran';
    const key = String(item.name) + '|' + jenis;
    if (!index[key]) {
      const row = sheet.getLastRow() + 1;
      sheet.getRange(row,1,1,6).setValues([[item.name,jenis,'Semua','Ya','Dibuat otomatis Finance Agent','']]);
      index[key] = row;
    }
    count++;
  });
  return count;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
