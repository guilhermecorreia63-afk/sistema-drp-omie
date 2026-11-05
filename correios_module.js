// Sanitiza textos para a codificação padrão WinAnsi (Helvetica) do PDFLib
function sanitizeWinAnsi(str) {
  if (!str) return "";
  let s = String(str)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // Remove acentos decompostos se houver
    .replace(/[\u2600-\u26FF]/g, "!") // Converte qualquer simbolo tipo aviso/triangulo (U+26A0, etc) para !
    .replace(/[\u2700-\u27BF]/g, "*") // Dingbats
    .replace(/\uFE0F/g, "")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\u2022/g, "-")
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/\u2026/g, "...")
    .replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, ""); // Remove emojis 4-bytes

  // Blindagem definitiva para fonte WinAnsi (Helvetica/StandardFonts): aceita apenas caracteres validos da tabela WinAnsi
  return s.replace(/[^\x20-\x7E\xA0-\xFF]/g, " ");
}

// Helper para quebra de linhas automática no PDF
function splitTextIntoLines(text, font, fontSize, maxWidth) {
  if (!text) return [];
  const sanitized = sanitizeWinAnsi(text);
  const words = sanitized.replace(/\r\n/g, "\n").split(/\s+/);
  const lines = [];
  let currentLine = "";

  for (const word of words) {
    const candidate = currentLine ? `${currentLine} ${word}` : word;
    try {
      const width = font.widthOfTextAtSize(candidate, fontSize);
      if (width <= maxWidth) {
        currentLine = candidate;
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    } catch (e) {
      currentLine = candidate;
    }
  }
  if (currentLine) lines.push(currentLine);
  return lines;
}

// 🚚 GERADOR DE RÓTULO TÉRMICO DEDICADO - ENTREGA PRÓPRIA (SOUZA - FORTALEZA / RMF)
async function gerarRotuloSouzaLocalPdf(item) {
  const { PDFDocument, rgb, StandardFonts } = PDFLib;
  const pdfDoc = await PDFDocument.create();

  const W = 283.46; // 100mm térmico (72 pt/in = 28.346 pt/cm)
  const H = 396.85; // 140mm térmico
  const page = pdfDoc.addPage([W, H]);

  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  const drawText = (text, options) => {
    const ptX = options.x;
    const ptY = H - options.yTop - (options.size || 8);
    page.drawText(sanitizeWinAnsi(text), { ...options, x: ptX, y: ptY });
  };

  const drawRect = (options) => {
    const ptX = options.x;
    const ptW = options.w;
    const ptH = options.h;
    const ptY = H - options.yTop - ptH;
    page.drawRectangle({
      x: ptX,
      y: ptY,
      width: ptW,
      height: ptH,
      color: options.color,
      borderColor: options.borderColor,
      borderWidth: options.borderWidth || 0
    });
  };

  const drawLine = (x1, yTop1, x2, yTop2, thickness = 0.6, color = rgb(0.1, 0.1, 0.1)) => {
    page.drawLine({
      start: { x: x1, y: H - yTop1 },
      end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
      thickness: thickness,
      color: color
    });
  };

  const drawBarcode = async (options, x, yTop, w, h) => {
    try {
      const canvas = document.createElement("canvas");
      bwipjs.toCanvas(canvas, options);
      const pngUrl = canvas.toDataURL("image/png");
      const pngImageBytes = await fetch(pngUrl).then(res => res.arrayBuffer());
      const pngImage = await pdfDoc.embedPng(pngImageBytes);
      page.drawImage(pngImage, { x: x, y: H - yTop - h, width: w, height: h });
    } catch (eBar) {
      console.error("Erro ao gerar barcode bwipjs (Souza):", eBar);
    }
  };

  const ped = item.dadosPedido || {};
  const destInfo = ped.destinatario || {};
  const enderInfo = destInfo.endereco || {};

  const destNome = (item.destinatario || destInfo.nome || "CLIENTE").toUpperCase();
  const destDoc = (destInfo.cpfCnpj || ped.cpf_cnpj_destinatario || item.cpf_cnpj || "").trim();
  const destLog = (enderInfo.logradouro || ped.logradouro || item.logradouro || "Rua").toUpperCase();
  const destNum = (enderInfo.numero || ped.numero || item.numero || "S/N").toUpperCase();
  const destCompl = (enderInfo.complemento || ped.complemento || item.complemento || "").toUpperCase();
  const destBairro = (enderInfo.bairro || ped.bairro || item.bairro || "").toUpperCase();
  const destCidade = (enderInfo.cidade || ped.cidade || item.cidade || "FORTALEZA").toUpperCase();
  const destUf = (enderInfo.uf || ped.uf || item.uf || "CE").toUpperCase();

  const destCepRaw = (enderInfo.cep || ped.cep || item.cep || "").replace(/\D/g, "");
  const destCep = destCepRaw.padStart(8, "0").substring(0, 8);
  const cepFmt = destCep.length === 8 ? `${destCep.substring(0,5)}-${destCep.substring(5)}` : destCep;

  const numPedido = ped.numero_pedido || item.pedido || "S/N";
  const numNf = item.nf || ped.numero_nf || "";
  const sroCode = (item.objeto || item.codigo_objeto || `SZ${String(numPedido).replace(/\D/g, '')}BR`).toUpperCase();
  const obsEntrega = (item.obs_entrega || ped.obs_entrega || ped.obs_venda || "").trim();

  // Borda Externa Térmica 100x140
  drawRect({ x: 8, yTop: 8, w: W - 16, h: H - 16, borderColor: rgb(0,0,0), borderWidth: 1.2 });

  // 1. CABEÇALHO MODERNO
  drawRect({ x: 8, yTop: 8, w: W - 16, h: 36, color: rgb(0.08, 0.12, 0.20) });
  drawText("COMUNIDADE CATOLICA SHALOM", { x: 16, yTop: 14, size: 9.5, font: fontBold, color: rgb(1,1,1) });
  drawText("ENTREGA LOCAL  -  ROBERTO SOUZA", { x: 16, yTop: 26, size: 8.5, font: fontBold, color: rgb(0.22, 0.74, 0.97) });

  // 2. PEDIDO & NOTA FISCAL
  drawRect({ x: 8, yTop: 44, w: W - 16, h: 22, color: rgb(0.94, 0.96, 0.98) });
  drawLine(8, 66, W - 8, 66, 0.8);
  drawText(`PEDIDO: #${numPedido}`, { x: 16, yTop: 51, size: 9.5, font: fontBold, color: rgb(0.1, 0.1, 0.1) });
  drawText(`NF-e: ${numNf ? numNf : 'S/N'}`, { x: 155, yTop: 51, size: 9.5, font: fontBold, color: rgb(0.1, 0.1, 0.1) });

  // 3. CÓDIGO DE RASTREIO BIPÁVEL (CODE 128)
  drawText("RASTREIO / BIPAGEM MOTORISTA:", { x: 16, yTop: 72, size: 7.5, font: fontBold, color: rgb(0.3, 0.3, 0.3) });
  if (sroCode) {
    await drawBarcode({
      bcid: 'code128',
      text: sroCode,
      scale: 3,
      height: 16,
      includetext: false
    }, 16, 82, W - 32, 42);
  }
  drawText(sroCode, { x: 75, yTop: 128, size: 11.5, font: fontBold, color: rgb(0, 0, 0) });
  drawLine(8, 142, W - 8, 142, 0.8);

  // 4. DESTINATÁRIO
  drawRect({ x: 8, yTop: 142, w: W - 16, h: 16, color: rgb(0.12, 0.16, 0.24) });
  drawText("DESTINATARIO (ENTREGA)", { x: 16, yTop: 146, size: 8, font: fontBold, color: rgb(1,1,1) });

  drawText(destNome.substring(0, 38), { x: 16, yTop: 164, size: 9, font: fontBold });
  if (destDoc) {
    drawText(`CPF/CNPJ: ${destDoc}`, { x: 16, yTop: 175, size: 7.2, font: fontReg, color: rgb(0.25, 0.25, 0.25) });
  }

  // Endereço de Entrega
  const linhaEnd = `${destLog}, ${destNum}${destCompl ? ' - ' + destCompl : ''}`;
  drawText(linhaEnd.substring(0, 48), { x: 16, yTop: 188, size: 8.5, font: fontBold });
  drawText(`BAIRRO: ${destBairro}`, { x: 16, yTop: 199, size: 8, font: fontReg });
  drawText(`${destCidade} - ${destUf}  |  CEP: ${cepFmt}`, { x: 16, yTop: 210, size: 8.5, font: fontBold });

  const foneDest = item.telefone || destInfo.telefone || destInfo.celular || ped.telefone_destinatario || "";
  if (foneDest) {
    drawText(`CONTATO: ${foneDest}`, { x: 16, yTop: 221, size: 7.5, font: fontBold, color: rgb(0.1, 0.3, 0.7) });
  }

  // 5. BOX DE CANHOTO / ASSINATURA DE RECEBIMENTO
  drawLine(8, 233, W - 8, 233, 0.8);
  drawText("CANHOTO DE ENTREGA / RECEBIMENTO:", { x: 16, yTop: 238, size: 7, font: fontBold });
  
  drawText("RECEBEDOR:", { x: 16, yTop: 250, size: 6.5, font: fontBold });
  drawLine(65, 256, W - 16, 256, 0.5);

  drawText("DOC / RG:", { x: 16, yTop: 264, size: 6.5, font: fontBold });
  drawLine(60, 270, 160, 270, 0.5);
  drawText("DATA:", { x: 170, yTop: 264, size: 6.5, font: fontBold });
  drawLine(195, 270, W - 16, 270, 0.5);

  drawText("ASSINATURA:", { x: 16, yTop: 278, size: 6.5, font: fontBold });
  drawLine(72, 286, W - 16, 286, 0.5);

  // 6. REMETENTE
  drawLine(8, 296, W - 8, 296, 0.8);
  drawText("REMETENTE: COMUNIDADE CATOLICA SHALOM - DIACONIA", { x: 16, yTop: 302, size: 7, font: fontBold });
  drawText("Estrada do Aquiraz, 501 - CE 040 KM 16 - Aquiraz/CE | CEP: 61700-000", { x: 16, yTop: 311, size: 6.2, font: fontReg });
  drawText("CNPJ: 07.044.456/0003-64 | Telefone: (85) 3218-7800", { x: 16, yTop: 320, size: 6.2, font: fontReg });

  // 7. RODAPÉ DE OBSERVAÇÃO
  drawLine(8, 330, W - 8, 330, 0.8);
  drawRect({ x: 8, yTop: 330, w: W - 16, h: H - 338, color: obsEntrega ? rgb(0.99, 0.95, 0.88) : rgb(0.96, 0.97, 0.98) });
  if (obsEntrega) {
    drawText("! ATENCAO: POSSUI OBSERVACOES ESPECIAIS (VER PAGINA 2)", { x: 14, yTop: 338, size: 6.8, font: fontBold, color: rgb(0.8, 0.2, 0) });
    drawText(obsEntrega.substring(0, 52), { x: 14, yTop: 349, size: 6.5, font: fontReg });
  } else {
    drawText("ENTREGA PROPRIA ROBERTO SOUZA - CONFERIR NOTA FISCAL NO ATO", { x: 14, yTop: 342, size: 6.8, font: fontBold, color: rgb(0.2, 0.2, 0.2) });
  }

  // =========================================================================
  // PÁGINA 2: ETIQUETA / SLIP DE OBSERVAÇÕES E RESTRIÇÕES DE ENTREGA (SOUZA)
  // =========================================================================
  if (obsEntrega) {
    const page2 = pdfDoc.addPage([W, H]);

    const drawText2 = (text, options) => {
      const ptX = options.x;
      const ptY = H - options.yTop - (options.size || 8);
      page2.drawText(sanitizeWinAnsi(text), { ...options, x: ptX, y: ptY });
    };

    const drawRect2 = (options) => {
      const ptX = options.x;
      const ptW = options.w;
      const ptH = options.h;
      const ptY = H - options.yTop - ptH;
      page2.drawRectangle({
        x: ptX,
        y: ptY,
        width: ptW,
        height: ptH,
        color: options.color,
        borderColor: options.borderColor,
        borderWidth: options.borderWidth || 0
      });
    };

    const drawLine2 = (x1, yTop1, x2, yTop2, thickness = 0.6, color = rgb(0.1, 0.1, 0.1)) => {
      page2.drawLine({
        start: { x: x1, y: H - yTop1 },
        end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
        thickness: thickness,
        color: color
      });
    };

    // Borda Externa Página 2
    drawRect2({ x: 8, yTop: 8, w: W - 16, h: H - 16, borderColor: rgb(0,0,0), borderWidth: 1.2 });

    // Cabeçalho de Destaque
    drawRect2({ x: 8, yTop: 8, w: W - 16, h: 36, color: rgb(0.85, 0.15, 0.15) });
    drawText2("INSTRUCOES DE ENTREGA - SOUZA", { x: 16, yTop: 14, size: 10, font: fontBold, color: rgb(1,1,1) });
    drawText2("VIA DE OBSERVACAO / ATENCAO ESPECIAL", { x: 16, yTop: 26, size: 7.8, font: fontBold, color: rgb(1,1,1) });

    // Mini Cabeçalho
    drawRect2({ x: 8, yTop: 44, w: W - 16, h: 26, color: rgb(0.95, 0.96, 0.98) });
    drawLine2(8, 70, W - 8, 70, 0.8);
    drawText2(`PEDIDO: #${numPedido}   |   NF: ${numNf || 'S/N'}`, { x: 16, yTop: 51, size: 9, font: fontBold });
    drawText2(`RASTREIO: ${sroCode}`, { x: 16, yTop: 61, size: 8, font: fontBold, color: rgb(0.1, 0.3, 0.7) });

    drawText2(`DESTINATARIO: ${destNome.substring(0, 36)}`, { x: 16, yTop: 78, size: 8.5, font: fontBold });
    drawText2(`ENDERECO: ${destLog}, ${destNum} ${destCompl}`, { x: 16, yTop: 89, size: 7.8, font: fontReg });
    drawText2(`BAIRRO: ${destBairro} - ${destCidade}/${destUf}`, { x: 16, yTop: 99, size: 7.8, font: fontReg });

    // Caixa de Destaque com as Observações
    drawRect2({ x: 14, yTop: 114, w: W - 28, h: 185, color: rgb(1, 0.98, 0.92), borderColor: rgb(0.85, 0.45, 0.1), borderWidth: 1.2 });
    drawText2("OBSERVACOES REGISTRADAS NO PEDIDO:", { x: 22, yTop: 122, size: 8.5, font: fontBold, color: rgb(0.7, 0.2, 0) });

    const lines = splitTextIntoLines(obsEntrega, fontBold, 9.2, W - 48);
    let curY = 140;
    for (const l of lines) {
      if (curY > 285) break;
      drawText2(l, { x: 22, yTop: curY, size: 9, font: fontBold, color: rgb(0.1, 0.1, 0.1) });
      curY += 14;
    }

    // Alerta Inferior para o Motorista
    drawRect2({ x: 8, yTop: 310, w: W - 16, h: H - 318, color: rgb(0.08, 0.12, 0.20) });
    drawText2("ATENCAO MOTORISTA / ENTREGADOR:", { x: 16, yTop: 318, size: 8, font: fontBold, color: rgb(1, 0.8, 0.2) });
    drawText2("- Entregar impreterivelmente conforme orientacoes acima.", { x: 16, yTop: 330, size: 7, font: fontReg, color: rgb(1,1,1) });
    drawText2("- Se houver recusa ou ausencia, entrar em contato com a Diaconia.", { x: 16, yTop: 341, size: 7, font: fontReg, color: rgb(1,1,1) });
    drawText2("- Bipar o codigo de rastreio SZ no app para confirmar entrega.", { x: 16, yTop: 352, size: 7, font: fontBold, color: rgb(0.4, 0.8, 1) });
  }

  const pdfBytes = await pdfDoc.save();
  return base64ArrayBuffer(pdfBytes);
}

async function gerarRotuloRetiradaLocalPdf(item) {
  const { PDFDocument, rgb, StandardFonts } = PDFLib;
  const pdfDoc = await PDFDocument.create();
  const W = 283.46;
  const H = 396.85;
  const page = pdfDoc.addPage([W, H]);
  const bold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const regular = await pdfDoc.embedFont(StandardFonts.Helvetica);
  const drawText = (text, x, yTop, size, font = regular, color = rgb(0.1, 0.1, 0.1)) => {
    page.drawText(sanitizeWinAnsi(text || ""), { x, y: H - yTop - size, size, font, color, maxWidth: W - x - 12 });
  };
  const drawLine = (y) => page.drawLine({ start: { x: 10, y: H - y }, end: { x: W - 10, y: H - y }, thickness: 0.7, color: rgb(0.55, 0.6, 0.66) });
  const service = String(item.servico || "").toUpperCase();
  const isGuarita = service === "RETIRADA_GUARITA";
  const titulo = isGuarita ? "RETIRADA NA GUARITA" : "RETIRADA NO ESTOQUE";
  const pedido = item.dadosPedido || {};
  const recipient = pedido.destinatario || {};
  const address = recipient.endereco || {};
  const observations = String(item.obs_entrega || pedido.obs_entrega || "").trim();
  page.drawRectangle({ x: 8, y: H - 8 - 42, width: W - 16, height: 42, color: rgb(0.08, 0.12, 0.2) });
  drawText("COMUNIDADE CATOLICA SHALOM", 16, 15, 10, bold, rgb(1, 1, 1));
  drawText(titulo, 16, 29, 9, bold, rgb(0.35, 0.82, 1));
  drawText(`PEDIDO: #${pedido.numero_pedido || item.pedido || "S/N"}`, 16, 62, 10, bold);
  drawText(`NF-e: ${item.nf || pedido.numero_nf || "S/N"}`, 16, 77, 8, regular);
  drawLine(92);
  drawText("RETIRADA LOCAL - SEM RASTREIO", 16, 101, 8, bold, rgb(0.15, 0.35, 0.55));
  drawText("DESTINATARIO", 16, 124, 7, bold, rgb(0.35, 0.4, 0.46));
  drawText(String(item.destinatario || recipient.nome || "CLIENTE").toUpperCase().slice(0, 44), 16, 137, 10, bold);
  drawText(`CPF/CNPJ: ${recipient.cpfCnpj || pedido.cpf_cnpj_destinatario || "-"}`, 16, 153, 7, regular);
  drawText(`PEDIDO / NF: ${pedido.numero_pedido || item.pedido || "S/N"} / ${item.nf || pedido.numero_nf || "S/N"}`, 16, 173, 7.5, regular);
  if (address.cep) drawText(`CEP: ${String(address.cep).replace(/(\d{5})(\d{3})/, "$1-$2")}`, 16, 188, 8, bold);
  drawText(titulo, 16, 220, 12, bold, rgb(0.04, 0.38, 0.62));
  drawLine(242);
  drawText("OBSERVACOES DO PEDIDO", 16, 256, 8, bold, rgb(0.65, 0.27, 0.05));
  const obsLines = splitTextIntoLines(observations || (isGuarita ? "Aguardar retirada do pedido na guarita." : "Retirada diretamente no estoque."), regular, 9, W - 32);
  let y = 273;
  for (const line of obsLines.slice(0, 7)) {
    drawText(line, 16, y, 8.5, regular);
    y += 13;
  }
  drawLine(354);
  drawText("CONFERIR PEDIDO E DOCUMENTO NO ATO DA RETIRADA", 16, 366, 6.5, bold);
  return base64ArrayBuffer(await pdfDoc.save());
}

// 🏷️ GERADOR UNIFICADO DE RÓTULOS (MÓDICO, PAC, SEDEX, MINI ENVIOS)
async function gerarRotuloPadronizadoInternoPdf(item, servicoOverride = null) {
  const { PDFDocument, rgb, StandardFonts } = PDFLib;
  const pdfDoc = await PDFDocument.create();

  const W = 300;
  const H = 453;
  const page = pdfDoc.addPage([W, H]);

  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  const drawTextTopPt = (text, options) => {
    const ptX = options.x;
    const ptY = H - options.yTop - (options.size || 8);
    page.drawText(sanitizeWinAnsi(text), { ...options, x: ptX, y: ptY });
  };

  const drawRectTopPt = (options) => {
    const ptX = options.x;
    const ptW = options.w;
    const ptH = options.h;
    const ptY = H - options.yTop - ptH;
    page.drawRectangle({
      x: ptX,
      y: ptY,
      width: ptW,
      height: ptH,
      color: options.color,
      borderColor: options.borderColor,
      borderWidth: options.borderWidth || 0
    });
  };

  const drawLineTopPt = (x1, yTop1, x2, yTop2, thickness = 0.5, color = rgb(0,0,0)) => {
    page.drawLine({
      start: { x: x1, y: H - yTop1 },
      end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
      thickness: thickness,
      color: color
    });
  };

  const drawBarcodeTopPt = async (options, x, yTop, w, h) => {
    try {
      const canvas = document.createElement("canvas");
      bwipjs.toCanvas(canvas, options);
      const pngUrl = canvas.toDataURL("image/png");
      const pngImageBytes = await fetch(pngUrl).then(res => res.arrayBuffer());
      const pngImage = await pdfDoc.embedPng(pngImageBytes);

      const ptX = x;
      const ptW = w;
      const ptH = h;
      const ptY = H - yTop - ptH;
      page.drawImage(pngImage, { x: ptX, y: ptY, width: ptW, height: ptH });
    } catch (eBar) {
      console.error("Erro ao gerar barcode bwipjs:", eBar);
    }
  };

  const ped = item.dadosPedido || {};
  const destInfo = ped.destinatario || {};
  const enderInfo = destInfo.endereco || {};

  const destNome = (item.destinatario || destInfo.nome || "CLIENTE").toUpperCase();
  const destLog = (enderInfo.logradouro || ped.logradouro || item.logradouro || "Rua").toUpperCase();
  const destNum = (enderInfo.numero || ped.numero || item.numero || "S/N").toUpperCase();
  const destCompl = (enderInfo.complemento || ped.complemento || item.complemento || "").toUpperCase();
  const destBairro = (enderInfo.bairro || ped.bairro || item.bairro || "").toUpperCase();
  const destCidade = (enderInfo.cidade || ped.cidade || item.cidade || "").toUpperCase();
  const destUf = (enderInfo.uf || ped.uf || item.uf || "CE").toUpperCase();

  const destCepRaw = (enderInfo.cep || ped.cep || item.cep || "").replace(/\D/g, "");
  const destCep = destCepRaw.padStart(8, "0").substring(0, 8);
  const cepFmt = destCep.length === 8 ? `${destCep.substring(0,5)}-${destCep.substring(5)}` : destCep;

  const origCep = "61700000";
  const numNf = item.nf || ped.numero_nf || "";
  const sroCode = (item.objeto || item.codigo_objeto || "YD156330147BR").toUpperCase();
  const cartaoPost = "0066578957";

  // Identificação do Serviço Real
  const servRaw = (servicoOverride || item.servico || "").toUpperCase();
  let servType = "MODICO";
  if (servRaw.includes("SEDEX") || sroCode.startsWith("AD")) servType = "SEDEX";
  else if (servRaw.includes("MINI") || sroCode.startsWith("AV")) servType = "MINI";
  else if (servRaw.includes("PAC") || sroCode.startsWith("AP")) servType = "PAC";

  // Configurações Específicas por Serviço
  let tituloServico = "IMPRESSO";
  let xTituloServico = 119.1;
  let simboloTopRight = null; // 'STANDARD', 'EXPRESSA', 'ECONOMICO'
  let simboloBotRightText = null; // 'PEA', 'SIM', '- - -'

  if (servType === "PAC") {
    tituloServico = "PAC";
    xTituloServico = 134.95;
    simboloTopRight = "STANDARD";
    simboloBotRightText = "PEA";
  } else if (servType === "SEDEX") {
    tituloServico = "SEDEX";
    xTituloServico = 128.55;
    simboloTopRight = "EXPRESSA";
    simboloBotRightText = "SIM";
  } else if (servType === "MINI") {
    tituloServico = "MINI_ENVIOS";
    xTituloServico = 113.27;
    simboloTopRight = "ECONOMICO";
    simboloBotRightText = "- - -";
  } else {
    // MÓDICO
    simboloTopRight = null;
    simboloBotRightText = "- - -";
  }

  // Payload Data Matrix de 160 Caracteres
  const somaCep = destCep.split("").reduce((acc, digit) => acc + parseInt(digit, 10), 0);
  const proximoMultiplo10 = Math.ceil(somaCep / 10) * 10;
  const validadorCep = String(proximoMultiplo10 - somaCep);

  const dComplDest = "00000";
  const dComplOrig = "00000";
  const idv = "51";
  const blocoFixo = `${destCep}${dComplDest}${origCep}${dComplOrig}${validadorCep}${idv}`;

  const sroPadded = sroCode.padEnd(13, " ").substring(0, 13);
  const servAdic = "25000000";
  const cartaoPadded = cartaoPost.padStart(10, "0").substring(0, 10);
  const codServ = servType === "SEDEX" ? "03220" : (servType === "PAC" ? "03298" : (servType === "MINI" ? "04227" : "20133"));
  const agrupamento = "00";

  let numEndClean = destNum.replace(/\D/g, "");
  if (!numEndClean || numEndClean === "") numEndClean = "0";
  const numLogrPadded = numEndClean.padStart(5, "0").substring(0, 5);

  const complLogrPadded = destCompl.padEnd(20, " ").substring(0, 20);
  const valDeclarado = "00000";
  const destTelRaw = (destInfo.fone || ped.fone || "").replace(/\D/g, "");
  const telDest = destTelRaw.length >= 10 ? destTelRaw.substring(0, 12).padEnd(12, "0") : "000000000000";
  const lat = "-00.000000";
  const lng = "-00.000000";
  const pipe = "|";
  const reservaCliente = "".padEnd(30, " ").substring(0, 30);

  const blocoVariavel = `${sroPadded}${servAdic}${cartaoPadded}${codServ}${agrupamento}${numLogrPadded}${complLogrPadded}${valDeclarado}${telDest}${lat}${lng}${pipe}${reservaCliente}`;
  const dataMatrixPayload = `${blocoFixo}${blocoVariavel}`;

  // RENDERIZAÇÃO DA GEOMETRIA EXATA DO PDF OFICIAL
  // Texto vertical lateral esquerda
  if (servType === "MODICO") {
    page.drawText("Fechamento Autorizado, pode ser aberto pelos Correios.", {
    x: 23,
    y: H - 294,
    size: 6.0,
    font: fontReg,
    rotate: PDFLib.degrees(90)
  });
  }

  // Data Matrix
  await drawBarcodeTopPt({
    bcid: 'datamatrix',
    text: dataMatrixPayload,
    scale: 3,
    padding: 0
  }, 126, 23, 39.0, 41.0);

    if (simboloTopRight === "STANDARD") {
    // Desenhar círculo PAC usando drawEllipse com x=222.25..252.25 (w=30, h=30) em yTop=22
    page.drawEllipse({ x: 237.25, y: H - 37, xScale: 15.0, yScale: 15.0, color: rgb(0,0,0) });
    drawTextTopPt("STANDARD", { x: 217, yTop: 63, size: 7.0, font: fontBold });
  } else if (simboloTopRight === "EXPRESSA") {
    // Simbolo EXPRESSA oficial
    const b64Str = "/9j/4AAQSkZJRgABAgAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCADIAKoDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigAooooAKKKKACiiobm5gs7d7i6njghQZeSVwqqPcngUATUV51rnxr8H6QzRwXM2pTLwVs48qP+BnAI9wTXEX/wC0VcsxGn+H4kUdGuLgtn8ABj86Ase+UV82v+0J4qLEppujBewMUpI/8iCrFt+0NryMPtejabKO4iLx5/MtQFj6KorxzSv2hNFuGCarpN5ZE8b4XEyj6/dP5A16PoPjDw/4mXOkarb3L4yYg22QfVGww/KgDcooooAKKKKACiiigAooooAKKKKACiiigAopCQBk14B8Vfi3JdST+H/DdxttlJS6vY2/1vqiH+76nv246gHW+O/jNpvhp5dP0dI9R1Ncqx3fuYT/ALRH3j7D8SOleA+IfFmueKboz6vqEs/OUiztjj/3UHA+vWsWigoKKKKACiiigAp0UrwSrJE7JIpBV1OCD7Gm0UAereDPjfrGitHaa8H1SxBA80n9/GP97+P6Nz719A6Fr+meJNNjv9Ku0uLdu6nlT6MOoPsa+KK3fCni7VfB2rrf6ZMQCcTQMcxzL6MP69RQKx9nUVz3hHxdpnjPRU1DT3wwws0DH54X9D/Q966GgQUUUUAFFFFABRRRQAUUVk+JNdtvDXh691e6P7u1jLBc4Lt0VR7k4H40AeY/Gz4gPpVt/wAIzpc5W8uEzdyIeY4z0Qe7d/b6188Va1LUbrVtTudQvZDJc3MjSSMe5P8AT2qrQUFFFFABRRRQAUUUUAFFFFABRRRQB0ngfxhe+C/EMWoWxZ7diEurfOBLH/iOoPr7E19d6ZqNrq+m2+oWUoltriMSRuO4P9a+IK9y+AXi5hJceFbuTKkG4s8nof40/wDZvwagTPeaKKKBBRRRQAUUUUAFeH/tCa+0drpnh+J8eaTdTgHB2j5U/Ancf+AivcK+UfjJqJ1D4mamu7MdqI7dPbCgn/x4tQNHBUUUUDCiiigAooooAKKKKACiiigAooooAK0vD+sS6B4h0/VoSd9pOshA6soPzL+IyPxrNooA+5oJ47q3jniYNFKodGHcEZBqWuN+FeonU/hpokzHLRwmA57eWxQfoorsqCQooooAKKKKACvjLxtKZ/HniCTduB1G4wR0I8xsfpX2bXxV4p/5G7Wv+v8An/8ARjUDRk0UUUDCirFjp95qd0lpYWs1zcOfljhjLsfwFep+HfgHruoKs2tXcOmRHny1/ey/odo/M/SgDySivqXSPgn4N01Vae0n1GUc77qU4/75XaPwINdbZ+FPDunqBaaFpsHulqgJ/HGaBXPi2ivueOGKEERRogPXauM1Wn0nTrldtxp9rKvpJCrD9RQFz4hor6+1H4ZeDNUVhP4es0LfxW6mEj/vgiuC1z9nvT5laTQtWntpOSIrtRIh9twwQPrmgLnz9RXT+J/h94l8JFn1LT2NsDgXUJ8yI8+o+79GArmKBhRRRQB9N/AZ2f4dFSchL2VR7DCn+teoV5d8BP8Akncn/X/L/wCgpXqNBLCiiigAooooAK+KvFP/ACN+tf8AX/P/AOjGr7Vr4q8U/wDI361/1/z/APoxqBoya9M8A/B/U/FKxajqhfT9JbBUlcSzL/sg9Af7x/AGup+FfwiRo4df8TW24nD2tjKvHs8g/kp/H0r3UAAYFAXMbw94X0bwtZfZdIsIrZSBucDLyf7zHk1tUUUCCiiigAooooAKKKKAGuiyIyOoZWGCCMgivKfG3wS0nW1lvNAEemagct5QGIJD7gfc+o49q9YooA+ItY0XUdA1KXT9UtJLa6j6o46j1B6EH1FUa+x/GHgvSfGmlGz1GLbKoJguUH7yFvUeo9R0P618qeK/Cup+ENak03Uo8MMtFKudkydmU/07UDPfvgJ/yTyT/r/l/wDQUr1GvLvgJ/yTuT/r/l/9BSvUaBMKKKKACiiigArw3wB8OV1Xxtq/ibVod1lBqU/2SFxxM4kb5z6qp6ep+nPuVMRFjUKihVHYDAoAfRRRQAUUUUAFFRT3ENrC89xNHDCgyzyMFVR7k9K4HWfjT4N0l2jjvJtQkXgizi3Af8CJCn8CaAPQ6K8Wm/aI0xWAg0C7dc9XmVf6Gr1h+0D4auJAl5Yaja5ON4VZFH1wc/kDQB63RWHoPi/w/wCJo92j6pb3LAZMQbbIPqhww/KtygAooooAK5jxx4MsvG3h+SwuQEuUBa1uMZMT+v0PQjuPcCunooA84+DGm3ejeEL3Tb+ExXVvqUqSIfXanT2PUGvR6aFCkkAAk5PHU06gAooooAKKKKACiiigAooooAK5Hxz4+0vwPpvmXTedfSg/Z7RD80h9T6L7n8M1reJvEFp4Y8PXmr3hzFbpkIDgux4VR7k4FfH3iDXr/wAS61capqMpeeds4z8qDsq+gFAGh4r8ca54xvDLql0fJBJjtY/lij+i9z7nJrnaKKCgooooAkgnmtZ0nt5XimjYMkkbbWU+oI5Fe2/Dz42yrLFpXiyUNGflj1EjBU+knqP9r888mvDqKAPulHWRFdGDKwyCDkEU6vDfgf4/kuCPCmpzF3RS1hI5ySo5MX4DkewI7CvcqCQooooAKKKKACiiigAooooAKKKKACiiigD5/wD2gvETy6lp3h6Fz5UCfap1HQu2QufoMn/gVeKV1/xRvGvviXrsjHOyfyh7BFC/+y1yFBQUUUUAFFFFABRRRQBa03ULjStTtdQtHKXFtIssbDsQQea+09H1KHWdGstSg/1V3Akyj0DAHFfEVfVnwZvGu/hjpgdstA0sRJ9A5I/QgUCZ39FFFAgooooAKKKKACiiigAooooAKKKKAMW48I+Gru5kuLnw9pM88jbnklso2Zie5JGSaj/4Qjwn/wBCvov/AIARf/E1vUUAYP8AwhHhP/oV9F/8AIv/AImj/hCPCf8A0K+i/wDgBF/8TW9RQBg/8IR4T/6FfRf/AAAi/wDiaP8AhCPCf/Qr6L/4ARf/ABNb1FAGD/whHhP/AKFfRf8AwAi/+Jo/4Qnwn/0LGi/+AEX/AMTW9RQBg/8ACE+E/wDoWNF/8AIv/ia1LDTrHS7YW2n2dvaQAlhFbxCNQT7DAq1RQAUUUUAFFFFABRRRQAUUUUAcVrPxU8JaBq1xpeoX8sd3bkLIgt3YAkA9QMdDUNh8XvBupaja2FrqEz3F1KkMSm2cZZiFAzjjk1yuk3mh2fxp8Ytrlzp0MbJCIzfOiqTtXpv7/SvQLHU/BV3fQw6ffaBNdlsxJbywtISOflCnORjtQBZh8V6TN4om8Nid01SKPzDC8TLuXAOVYjB4Pb39Kl8QeJNL8L6aL/VrnyIC4jXClmZj2AHJ9a4z4saBd/Z7Pxjoo26vojeaSBkyQjlgfUDk/Qt61j+HriX4seNoNfuLd4vD2iqv2aCTnzLkgMSex2nB/BfU0Adv4g+InhzwvPbQ6vczW8txCJ408h2O0kjnAODx0NZ9j8YPBN/eR2ser+W8h2qZoHRc+hYjA/HFZfiCCG5+PPhyK4ijljOmS5R1DA/6zsak+L2l+Hbf4fX8lxaWcFyNv2RkjVZDJuHC45PGc+2aAOp8UeNtD8HG1/tq5eD7Vv8AK2xM+7bjd90HH3hWAnxq8DO4X+1ZVBONzWsmB/47XKavOYrv4RzatIiYgczPOwAH7uH7xP65713PiTWfAz+Hr5dRvdHntvKbdGksbuTg42gZO70xQBu33iLS9P8ADr69NdK2mrGsnnxDeCpIAIx16iuS/wCF2eBv+gnP/wCAsn+FcZp0dzH+zFei4DhW3NDu/uGYdPbOTXb+HtZ8CR+GtKS41Lw6sy2cQkWWeAMG2DOcnOc0DOh8NeMNF8W209xo9y0sUDBJGeJkwSM9wK5fUPjX4M0+/a0F1c3OxtrTW8O6MH6kjP1Ga29VWy1XwLri+FZLKZ5rWaONrBkYNJsPy5TjdyB+Iri/hj4v8FW3hS10S5ktNOv1Ux3cV4gTzXyckseDn0J46UCPTdF1zTfEOmR6jpV2lzayfddcgg9wQeQR6GuS1v4w+EdD1KSwlup7maJishtot6oR1BJIBx7Zqz4X8FnwuniJ9Kv1a11RvOsreNcLbNhujZOc5XtwFFcR8KPFPhXw/okmh6yYtM1tJpEu2vI9vmkserngYGBgkdPegD1Xw74m0nxVpov9Iu1nhB2sMbWRvRgeQaZ4k8U6R4S0+O91i4MEEkgiQqhcliCeg56A1j+GPB1rovivVte0m9h/szVI0K2dug8sOOrhgcdd3AH8RrmPG9gvjr4m2PhUuDaafp81zckfwySLtT8QTGfxNAHqltcRXlpDcwOHhmRZI3H8SkZB/Kpq8/8Ag9q0uoeBo7C6yLzSpnsZlbqNp+UfgCB/wGvQKACiiigAooooA8X03wzo3if4z+MINZsUu44UhZFZmXBKqOxFd/pnw68JaNqUOoafo0UF3CSY5FkclcgjuxHQ1z2sfCu71DxTqGu2Hi3UdKlvivmJaKV4AAwWDjPTNMtvhhr0F1DM/wARtelSORXMbSOQ4B6H950PSgZY+KfiG5hs7Xwpox3a1rbeSgU4MUROGc+meRn03HtXO+EEuPhd49/4RK+naXSNXCyWVw4wBNgAj2yflx/uetdzpXgiKy8b6h4rvb5r6+uF8uBWiCrbJ6Lye2Bnjv6mpvG/gu08baTFaTzta3EEolt7qNctEe/pwR7+h7UCOE+IXhqz8W/F/QdHv5J47ebTXZmgZVcFTIwxkEdvStjSvgb4Q0y9juZFvr4xtuEd3KpQn3CquR7H8a6AeD3k8XaP4iutTaa60+zNq6iEKJiQcueeD82cV1dAHlPxT0uz1fxt4D02+h820nnuUkjDFdwxF3Ugj8KwviH8MdK8LWUHibw/pqvFYyK93YTM00cseRz8xJ4789DnjFen694UTXfEegau120LaPJJIsYTcJd+3gnPGNvv1reubeK7tZba4jWSGZDHIjdGUjBB/CgDz3xtqtlrfwOvtR04KtpPaRGNFA/d/Og2ccDaQRjtineH/hf4Lu/Del3M+hQvNNaRSSOZJBligJP3vWn2HwvFh4J1fwqutTSWN9IHiZ4Rut+QSOvzZ2j07nvWdF8JddgiSGH4j69HEihURHcKoHAAHmcCgZ1V6ul/DfwZfXelaUfslsfPa2hc5YkhSctnoOfwqjP4S8H/ABD0e11qfSoS97CsouIWKSAkd2XG4g8c56Vb8NeDbjR9P1Gy1jXr3X4b1QjLfMzBVwQyjLNwc+3SuSHwe1XS5pIvDfjfUtL0+Vi32YBm2Z7gh1BP4A+9Aip4IuZfA+veNdBhmuNS0rR7cXkCFgWU7dzIPcg447r2zXVWuk+E/il4dtdbvNHgd7hCCwYrLGwJBUuuCcEd/wCtaXg7wPp3g7Tri3geW7uLt991c3HLzH39uTx7muSn+D95p+oTz+E/Ft9ottcPue1QMyg+xDDp2yCfegCp4M08eCPivqXhewvZp9HlsPthjmcHyHyvJ6Dp3x0Zc9M1i+Fo/HWva1rvi/wy2mRQ6ldNEGvc7jGn3ccHjBA+q13ui/DG30XRtXhXVrq41fVYWhuNUmXc4BGDtBPHXPJJzjngV0vhbw/B4W8NWei27mSO2UjzCuC5JLE49yTQM8u8BHWfCvxY1DSPEP2ZbjXoDeA2x/dtKCx46Y48zP4V7VXKeJvBkfiDX9D1mO9ezu9KlMissYbzVyDsPI44P/fRrq6BBRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH//ZCg==";
    const imgBytes = Uint8Array.from(atob(b64Str), c => c.charCodeAt(0));
    const expressaImg = await pdfDoc.embedJpg(imgBytes);
    page.drawImage(expressaImg, { x: 216, y: H - 22 - 50, width: 42.5, height: 50 });
  } else if (simboloTopRight === "ECONOMICO") {
    drawRectTopPt({ x: 222.25, yTop: 22, w: 30, h: 30, color: rgb(0,0,0) });
    drawTextTopPt("ECONÔMICO", { x: 215, yTop: 63, size: 7.0, font: fontBold });
  }
  // NF, Contrato, PP, Peso
  drawTextTopPt(`NF: ${numNf ? numNf + ' - 1' : '-'}`, { x: 27, yTop: 72.68, size: 8.0, font: fontReg });
  drawTextTopPt("Contrato: 9912293215 / 66578957", { x: 27, yTop: 82.68, size: 8.0, font: fontBold });

  const ppReal = item.pp || ped.pp || "";
  const ppText = ppReal ? `PP: ${ppReal}` : "PP: -";
  drawTextTopPt(ppText, { x: 27, yTop: 93.68, size: 8.0, font: fontReg });

  drawTextTopPt("Peso", { x: 188, yTop: 82.68, size: 8.0, font: fontReg });

  // Nome do Serviço (IMPRESSO, PAC, SEDEX, MINI_ENVIOS)
  drawTextTopPt(tituloServico, { x: xTituloServico, yTop: 92.48, size: 10.0, font: fontBold });

  // Rastreio Visível
  const sroFmt = sroCode.length === 13 ? `${sroCode.substring(0,2)}${sroCode.substring(2,5)}${sroCode.substring(5,8)}${sroCode.substring(8,11)}${sroCode.substring(11,13)}` : sroCode;
  const xRastreioVisivel = servType === "SEDEX" ? 100.09 : 100.4;
  drawTextTopPt(sroFmt, { x: xRastreioVisivel, yTop: 105.06, size: 11.0, font: fontBold });

  // RM (se for Módico)
  if (servType === "MODICO") {
    drawTextTopPt("RM", { x: 268.56, yTop: 130.68, size: 8.0, font: fontBold });
  }

  // Barcode Principal GS1-128
  await drawBarcodeTopPt({
    bcid: 'gs1-128',
    text: `(91)${sroCode}`,
    scale: 2,
    height: 15,
    includetext: false
  }, 40, 122, 220, 52);

  // Recebedor / Assinatura / Documento
  drawTextTopPt("Recebedor", { x: 34, yTop: 179.53, size: 7.0, font: fontReg });
  drawLineTopPt(74, 188.5, 266, 188.5, 0.5);

  drawTextTopPt("Assinatura", { x: 34, yTop: 190.53, size: 7.0, font: fontReg });
  drawLineTopPt(74, 198.5, 155, 198.5, 0.5);

  drawTextTopPt("Document", { x: 156, yTop: 190.53, size: 7.0, font: fontReg });
  drawLineTopPt(195, 198.5, 266, 198.5, 0.5);

  // ENTREGA NO VIZINHO e NÃO AUTORIZADA
  drawRectTopPt({ x: 35, yTop: 200, w: 231, h: 9, color: rgb(0,0,0) });
  drawTextTopPt("ENTREGA NO VIZINHO", { x: 35, yTop: 200.28, size: 7.0, font: fontBold, color: rgb(1,1,1) });
  drawTextTopPt("NÃO AUTORIZADA", { x: 35, yTop: 209.53, size: 7.0, font: fontReg });

  // DESTINATÁRIO
  drawRectTopPt({ x: 27, yTop: 219, w: 254, h: 130, borderColor: rgb(0,0,0), borderWidth: 1.0 });
  drawRectTopPt({ x: 34, yTop: 219, w: 98, h: 11, color: rgb(0,0,0) });
  drawTextTopPt("DESTINATÁRIO", { x: 53, yTop: 219.68, size: 8.0, font: fontBold, color: rgb(1,1,1) });

  drawTextTopPt(`${destNome} -`, { x: 35, yTop: 237.18, size: 8.0, font: fontReg });
  drawTextTopPt(`${destLog}, ${destNum}`, { x: 35, yTop: 254.04, size: 8.0, font: fontReg });
  if (destCompl || destBairro) {
    const bLine = `${destCompl ? destCompl + ' ' : ''}${destBairro}`;
    drawTextTopPt(bLine.substring(0, 48), { x: 35, yTop: 263.77, size: 8.0, font: fontReg });
  }
  drawTextTopPt(cepFmt, { x: 35, yTop: 286.28, size: 7.0, font: fontBold });
  drawTextTopPt(`${destCidade} / ${destUf}`, { x: 109, yTop: 285.68, size: 8.0, font: fontReg });
  drawTextTopPt("Brasil", { x: 157, yTop: 296.28, size: 7.0, font: fontReg });

  // Barcode CEP Code 128C
  if (destCep.length === 8) {
    await drawBarcodeTopPt({
      bcid: 'code128',
      text: destCep,
      scale: 2,
      height: 15,
      includetext: false
    }, 35, 298, 106, 48);
  }

  // Observações
  drawTextTopPt("Obs: Email do Destinatario:", { x: 156, yTop: 314.03, size: 6.0, font: fontReg });
  const emailDest = item.email || destInfo.email || ped.email || 'gabrielpsantos.bel@gmail.com; Inf.';
  drawTextTopPt(emailDest.substring(0, 42), { x: 156, yTop: 321.32, size: 6.0, font: fontReg });
  drawTextTopPt("Contribuinte: Produto destinado a Consumid", { x: 156, yTop: 328.62, size: 6.0, font: fontReg });

  // Bloco Remetente
  drawTextTopPt("Remetente:", { x: 28, yTop: 350.68, size: 8.0, font: fontBold });
  drawTextTopPt("ASSOCIACAO SHALOM", { x: 28, yTop: 360.68, size: 8.0, font: fontBold });
  drawTextTopPt("Sem Departamento", { x: 28, yTop: 370.04, size: 7.0, font: fontReg });
  drawTextTopPt("ESTRADA DO AQUIRAZ, 501, , 501, CE 040 KM16, -", { x: 28, yTop: 379.04, size: 7.0, font: fontReg });
  drawTextTopPt("LAGOA DO JUNCO", { x: 28, yTop: 387.54, size: 7.0, font: fontReg });
  drawTextTopPt("61700-000", { x: 28, yTop: 397.68, size: 8.0, font: fontBold });
  drawTextTopPt("AQUIRAZ / CE", { x: 102, yTop: 398.89, size: 6.0, font: fontReg });

  // Símbolo / Marcador Inferior Direito (PEA, SIM, - - -)
  drawRectTopPt({ x: 251, yTop: 351, w: 30, h: 58, color: rgb(0,0,0) });
  if (simboloBotRightText === "PEA") {
    // Texto PEA vertical 18pt Helvetica-Bold inteiramente visível e centralizado
    page.drawText("PEA", {
      x: 275,
      y: H - 398,
      size: 18.0,
      font: fontBold,
      color: rgb(1,1,1),
      rotate: PDFLib.degrees(90)
    });
  } else if (simboloBotRightText === "SIM") {
    // Texto SIM vertical 18pt Helvetica-Bold inteiramente visível e centralizado
    page.drawText("SIM", {
      x: 275,
      y: H - 397,
      size: 18.0,
      font: fontBold,
      color: rgb(1,1,1),
      rotate: PDFLib.degrees(90)
    });
  } else {
    // 3 marcas brancas para Módico e Mini
    drawRectTopPt({ x: 264.5, yTop: 372, w: 3, h: 6, color: rgb(1,1,1) });
    drawRectTopPt({ x: 264.5, yTop: 383, w: 3, h: 6, color: rgb(1,1,1) });
    drawRectTopPt({ x: 264.5, yTop: 394, w: 3, h: 6, color: rgb(1,1,1) });
  }

  // Página 2 para Correios / Módico se houver observações de entrega
  const obsModico = (item.obs_entrega || ped.obs_entrega || ped.obs_venda || "").trim();
  if (obsModico) {
    const page2 = pdfDoc.addPage([W, H]);
    const drawTextMod2 = (text, options) => {
      const ptX = options.x;
      const ptY = H - options.yTop - (options.size || 8);
      page2.drawText(sanitizeWinAnsi(text), { ...options, x: ptX, y: ptY });
    };
    page2.drawRectangle({ x: 10, y: 10, width: 280, height: 433, borderColor: rgb(0,0,0), borderWidth: 1.5 });
    page2.drawRectangle({ x: 10, y: H - 52, width: 280, height: 42, color: rgb(0.12, 0.25, 0.45) });
    drawTextMod2("INSTRUCOES / OBSERVACOES DO PEDIDO", { x: 22, yTop: 18, size: 10, font: fontBold, color: rgb(1,1,1) });
    drawTextMod2(`PEDIDO: #${numNf || item.pedido || "S/N"}  |  RASTREIO: ${sroCode}`, { x: 22, yTop: 32, size: 8, font: fontBold, color: rgb(1,1,1) });
    drawTextMod2(`DESTINATARIO: ${destNome.substring(0, 42)}`, { x: 16, yTop: 65, size: 8.5, font: fontBold });
    drawTextMod2(`ENDERECO: ${destLog}, ${destNum} ${destCompl}`, { x: 16, yTop: 78, size: 8, font: fontReg });
    drawTextMod2(`${destCidade}/${destUf} - CEP: ${cepFmt}`, { x: 16, yTop: 90, size: 8, font: fontReg });
    page2.drawRectangle({ x: 16, y: H - 380, width: 268, height: 260, color: rgb(1, 0.98, 0.92), borderColor: rgb(0.85, 0.45, 0.1), borderWidth: 1.5 });
    drawTextMod2("OBSERVACOES REGISTRADAS:", { x: 24, yTop: 130, size: 8.5, font: fontBold, color: rgb(0.7, 0.2, 0) });
    const linesMod = splitTextIntoLines(obsModico, fontBold, 9.5, 250);
    let curY = 150;
    for (const l of linesMod) {
      if (curY > 360) break;
      drawTextMod2(l, { x: 24, yTop: curY, size: 9.5, font: fontBold });
      curY += 15;
    }
  }

  const pdfBytes = await pdfDoc.save();
  return base64ArrayBuffer(pdfBytes);
}

// Manter compatibilidade com a função Módico chamando o gerador padronizado
async function gerarRotuloModicoInternoPdf(item) {
  return await gerarRotuloPadronizadoInternoPdf(item, "MODICO");
}

// Helper seguro para parsing de respostas HTTP (Evita "Unexpected token 'E'... is not valid JSON")
async function safeFetchJson(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch (eJson) {
      const rawText = await response.text();
      return { ok: false, error: "JSON_PARSE_ERROR", message: rawText.substring(0, 300) };
    }
  } else {
    const rawText = await response.text();
    return { ok: false, error: "HTTP_NON_JSON_RESPONSE", message: rawText.substring(0, 300) };
  }
}

let todosPedidos = [];
let etiquetasGeradas = [];
let filtroAtual = "TODOS";

document.addEventListener("DOMContentLoaded", () => {
  try { initDashboard(); } catch (e) { console.error("initDashboard:", e); }
  try { initFaturadosTab(); } catch (e) { console.error("initFaturadosTab:", e); }
  try { initGeradasTab(); } catch (e) { console.error("initGeradasTab:", e); }
  try { initArquivoTab(); } catch (e) { console.error("initArquivoTab:", e); }
  try { if (typeof initXmlImport === "function") initXmlImport(); } catch (e) { console.error("initXmlImport:", e); }
  try { if (typeof initRangesModico === "function") initRangesModico(); } catch (e) { console.error("initRangesModico:", e); }
  try { if (typeof initPlpTab === "function") initPlpTab(); } catch (e) { console.error("initPlpTab:", e); }
  try { if (typeof initManualTab === "function") initManualTab(); } catch (e) { console.error("initManualTab:", e); }
});

async function carregarEtiquetasDoTurso() {
  try {
    const res = await fetch("/.netlify/functions/turso-db?action=list_prepostagens");
    const data = await safeFetchJson(res);
    if (!res.ok || data.ok === false || data.error) {
      console.error("Erro ao carregar pré-postagens do Turso:", data);
      const tbody = document.getElementById("tableBodyAguardando");
      if (tbody) {
        const errMsg = data.error || data.message || `Status HTTP ${res.status}`;
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: #f87171;">
          ⚠️ Erro ao consultar pré-postagens no Turso DB: <strong>${errMsg}</strong><br>
          <small style="color: #94a3b8;">Verifique se as variáveis <code>CORREIOS_TURSO_URL</code> e <code>CORREIOS_TURSO_TOKEN</code> estão configuradas na Vercel (Project Settings &rarr; Environment Variables) com o banco gestoretiquetas.</small>
        </td></tr>`;
      }
      return;
    }
    if (data.prepostagens && data.prepostagens.length > 0) {
      etiquetasGeradas = data.prepostagens.filter(p => {
        const estaCancelado = p.cancelado === 1 || p.cancelado === "1" || p.cancelado === true || p.status_cancelamento === "CANCELADO";
        const statusImp = (p.status_impressao || "PENDENTE").toUpperCase();
        return (statusImp === "PRONTO" || statusImp === "PENDENTE" || !p.status_impressao) && !estaCancelado;
      })
        .map(p => ({
          statusImpressao: p.status_impressao || "PENDENTE",
          cancelado: p.cancelado || 0,
        idPrePostagem: p.id_prepostagem,
        objeto: p.codigo_objeto || `OBJ_${p.id}`,
        servico: p.servico,
        destinatario: p.destinatario,
        cidadeUf: `${p.cidade || ''}/${p.uf || ''}`,
        nf: p.numero_nf,
        chaveNfe: p.chave_nfe || "",
        data: p.created_at ? new Date(p.created_at).toLocaleTimeString() : new Date().toLocaleTimeString(),
        idRecibo: p.id_recibo_atual,
        statusRotulo: p.status_rotulo || "PENDENTE",
        obs_entrega: p.obs_entrega || "",
        pdfBase64: null,
        dadosPedido: {
          numero_pedido: p.pedido,
          numero_nf: p.numero_nf,
          chave_nfe: p.chave_nfe,
          forma_envio: p.servico,
          obs_entrega: p.obs_entrega || "",
          destinatario: {
            nome: p.destinatario,
            cpfCnpj: p.cpf_cnpj_destinatario,
            endereco: {
              logradouro: p.logradouro,
              numero: p.numero,
              complemento: p.complemento || "",
              bairro: p.bairro || "",
              cidade: p.cidade,
              uf: p.uf,
              cep: p.cep
            }
          }
        }
      }));
      renderEtiquetasGeradas();
    } else {
      etiquetasGeradas = [];
      renderEtiquetasGeradas();
    }
  } catch (err) {
    console.error("Erro ao carregar etiquetas do Turso no F5:", err);
  }
  try {
    await carregarEtiquetasTotalExpress();
  } catch (eTotal) {
    console.error("Erro Total Express:", eTotal);
  }
}

// Navegação integrada via sidebar principal do DRP Omie

// ABA 1: EXPEDIÇÕES FATURADAS (FONTE PRINCIPAL TURSO PRATA)
let expedicoesPrataState = {
  pagina: 1,
  limit: 25,
  periodo: "3d",
  tipoOrigem: "TODOS",
  transportadora: "TODOS",
  busca: "",
  dataInicio: "",
  dataFim: "",
  listaExpedicoes: [],
  totalPaginas: 1
};

// todosPedidos re-used from top declaration

function initFaturadosTab() {
  const btnBuscarPrata = document.getElementById("btnBuscarPrata");
  const btnAtualizarOmie = document.getElementById("btnAtualizarOmie");
  const btnEmitirLote = document.getElementById("btnEmitirLote");
  const chkSelectAll = document.getElementById("chkSelectAll");
  const inputBuscaPrata = document.getElementById("inputBuscaPrata");
  const selectPageLimit = document.getElementById("selectPageLimit");
  const btnPagAnterior = document.getElementById("btnPagAnterior");
  const btnPagProxima = document.getElementById("btnPagProxima");
  const inputDataInicio = document.getElementById("inputDataInicio");
  const inputDataFim = document.getElementById("inputDataFim");

  // Chips Período
  document.querySelectorAll("#periodoChips .chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#periodoChips .chip").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      expedicoesPrataState.periodo = btn.dataset.periodo;
      if (btnAtualizarOmie) {
        if (btn.dataset.periodo === "hoje") btnAtualizarOmie.textContent = "↻ Atualizar do Omie (Hoje)";
        else if (btn.dataset.periodo === "ontem") btnAtualizarOmie.textContent = "↻ Atualizar do Omie (Ontem e Hoje)";
        else if (btn.dataset.periodo === "3d") btnAtualizarOmie.textContent = "↻ Atualizar do Omie (Últimos 3 dias)";
        else btnAtualizarOmie.textContent = `↻ Atualizar do Omie (${btn.textContent})`;
      }
      carregarExpedicoesPrata(1);
    });
  });

  // Chips Tipo Origem
  document.querySelectorAll("#tipoOrigemChips .chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#tipoOrigemChips .chip").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      expedicoesPrataState.tipoOrigem = btn.dataset.origem;
      carregarExpedicoesPrata(1);
    });
  });

  // Chips Transportadora
  document.querySelectorAll("#filterChips .chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#filterChips .chip").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      expedicoesPrataState.transportadora = btn.dataset.filter;
      carregarExpedicoesPrata(1);
    });
  });

  // Busca Local (Turso)
  if (btnBuscarPrata) {
    btnBuscarPrata.addEventListener("click", () => {
      expedicoesPrataState.busca = inputBuscaPrata ? inputBuscaPrata.value.trim() : "";
      expedicoesPrataState.dataInicio = inputDataInicio ? inputDataInicio.value : "";
      expedicoesPrataState.dataFim = inputDataFim ? inputDataFim.value : "";
      carregarExpedicoesPrata(1);
    });
  }

  if (inputBuscaPrata) {
    inputBuscaPrata.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        expedicoesPrataState.busca = inputBuscaPrata.value.trim();
        carregarExpedicoesPrata(1);
      }
    });
  }

  // Sincronizar do Omie
  if (btnAtualizarOmie) {
    btnAtualizarOmie.addEventListener("click", sincronizarComOmie);
  }

  // Paginação
  if (selectPageLimit) {
    selectPageLimit.addEventListener("change", () => {
      expedicoesPrataState.limit = Number(selectPageLimit.value);
      carregarExpedicoesPrata(1);
    });
  }

  if (btnPagAnterior) {
    btnPagAnterior.addEventListener("click", () => {
      if (expedicoesPrataState.pagina > 1) {
        carregarExpedicoesPrata(expedicoesPrataState.pagina - 1);
      }
    });
  }

  if (btnPagProxima) {
    btnPagProxima.addEventListener("click", () => {
      if (expedicoesPrataState.pagina < expedicoesPrataState.totalPaginas) {
        carregarExpedicoesPrata(expedicoesPrataState.pagina + 1);
      }
    });
  }

  if (chkSelectAll) {
    chkSelectAll.addEventListener("change", (e) => {
      document.querySelectorAll(".chk-pedido").forEach(chk => {
        chk.checked = e.target.checked;
      });
      atualizarBotaoEmissao();
    });
  }

  if (btnEmitirLote) {
    btnEmitirLote.addEventListener("click", emitirSelecionados);
  }

  // ABRIR ABA 1: CONSULTA TURSO IMEDIATA (ZERO CHAMADAS AO OMIE)
  carregarExpedicoesPrata(1);
}

async function carregarExpedicoesPrata(pagina = 1) {
  const tableBody = document.getElementById("tableBody");
  const totalCount = document.getElementById("totalCount");
  const lblUltimaAtualizacaoOmie = document.getElementById("lblUltimaAtualizacaoOmie");
  const lblPaginacaoInfo = document.getElementById("lblPaginacaoInfo");
  const btnPagAnterior = document.getElementById("btnPagAnterior");
  const btnPagProxima = document.getElementById("btnPagProxima");

  expedicoesPrataState.pagina = pagina;

  if (tableBody) {
    tableBody.innerHTML = `<tr><td colspan="9" class="empty-state">⏳ Carregando expedições do Turso DB...</td></tr>`;
  }

  try {
    const params = new URLSearchParams({
      action: "list_expedicoes_prata",
      page: pagina.toString(),
      limit: expedicoesPrataState.limit.toString(),
      busca: expedicoesPrataState.busca,
      tipo_origem: expedicoesPrataState.tipoOrigem,
      periodo: expedicoesPrataState.periodo,
      data_inicio: expedicoesPrataState.dataInicio,
      data_fim: expedicoesPrataState.dataFim,
      transportadora: expedicoesPrataState.transportadora
    });

    const res = await fetch(`/.netlify/functions/turso-db?${params.toString()}`);
    const data = await safeFetchJson(res);

    if (!res.ok || data.ok === false || data.error) {
      const errMsg = data.error || data.message || `Status HTTP ${res.status}`;
      if (tableBody) {
        tableBody.innerHTML = `<tr><td colspan="9" class="empty-state" style="color: #f87171;">
          ⚠️ Erro ao consultar expedições no Turso DB: <strong>${errMsg}</strong><br>
          <small style="color: #94a3b8;">Se estiver acessando via Vercel, certifique-se de configurar as variáveis de ambiente <code>CORREIOS_TURSO_URL</code> e <code>CORREIOS_TURSO_TOKEN</code> no painel da Vercel (Project Settings &rarr; Environment Variables) com o banco gestoretiquetas.</small>
        </td></tr>`;
      }
      return;
    }

    const expedicoes = data.expedicoes || [];
    expedicoesPrataState.listaExpedicoes = expedicoes;
    expedicoesPrataState.totalPaginas = data.total_paginas || 1;

    // Atualizar total e info de sync
    if (totalCount) totalCount.textContent = data.total_registros || expedicoes.length;
    if (lblUltimaAtualizacaoOmie && data.ultima_atualizacao_omie) {
      const u = data.ultima_atualizacao_omie;
      const dtStr = u.finalizado_em ? u.finalizado_em.replace('T', ' ').substring(0, 16) : '--/--/----';
      lblUltimaAtualizacaoOmie.innerHTML = `${dtStr} <small style="color: #94a3b8;">(Novos: ${u.novos || 0}, Erros: ${u.erros || 0})</small>`;
    }

    // Mapear para todosPedidos para permitir emissão de rótulo/prepostagem
    todosPedidos = expedicoes.map(item => ({
      numero_pedido: item.tipo_origem === 'PEDIDO' ? (item.numero_pedido || item.codigo_pedido_omie) : (item.numero_remessa || item.codigo_remessa_omie),
      numero_remessa: item.numero_remessa,
      tipo_origem: item.tipo_origem,
      numero_nf: item.numero_nf,
      serie_nf: item.serie_nf || "1",
      chave_nfe: item.chave_nfe,
      data_emissao: item.data_emissao,
      destinatario: {
        nome: item.cliente_nome,
        cpfCnpj: item.cliente_cpf_cnpj,
        telefone: item.telefone_destinatario || "",
        email: item.email_destinatario || "",
        endereco: {
          logradouro: item.logradouro,
          numero: item.numero,
          complemento: item.complemento,
          bairro: item.bairro,
          cidade: item.cidade,
          uf: item.uf,
          cep: item.cep
        }
      },
      valor_nf: item.valor_nf,
      valor_frete: item.valor_frete,
      peso_kg: item.peso_kg,
      data_emissao: item.data_emissao,
      serie_nf: item.serie_nf,
      codigo_nf: item.codigo_nf,
      telefone_destinatario: item.telefone_destinatario || "",
      email_destinatario: item.email_destinatario || "",
      natureza: item.natureza || "",
      obs_venda: item.obs_venda,
      codigo_transportadora: item.codigo_transportadora,
      forma_envio: item.servico_normalizado || "PAC",
      forma_envio_raw: item.transportadora_normalizada || "Outros",
      servico: item.servico_normalizado || "PAC",
      transportadora_normalizada: item.transportadora_normalizada,
      qtd_etiquetas: 1
    }));

    // Renderizar tabela
    if (expedicoes.length === 0) {
      if (tableBody) {
        tableBody.innerHTML = `<tr><td colspan="9" class="empty-state">Nenhuma expedição encontrada na base local para os filtros selecionados.</td></tr>`;
      }
    } else {
      renderTabelaPrata(expedicoes);
    }

    // Atualizar Paginação UI
    if (lblPaginacaoInfo) {
      lblPaginacaoInfo.textContent = `Página ${data.pagina || 1} de ${data.total_paginas || 1} (${data.total_registros || 0} registros)`;
    }
    if (btnPagAnterior) btnPagAnterior.disabled = (data.pagina || 1) <= 1;
    if (btnPagProxima) btnPagProxima.disabled = (data.pagina || 1) >= (data.total_paginas || 1);

  } catch (err) {
    console.error("Erro ao carregar expedições da Prata:", err);
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="9" class="empty-state" style="color: #f87171;">Erro ao carregar dados do Turso DB: ${err.message}</td></tr>`;
    }
  }
}


function atualizarBotaoEmissao() {
  const btnEmitirLote = document.getElementById("btnEmitirLote");
  if (!btnEmitirLote) return;
  const selecionados = document.querySelectorAll(".chk-pedido:checked").length;
  btnEmitirLote.disabled = selecionados === 0;
  if (selecionados > 0) {
    btnEmitirLote.textContent = `🚀 Gerar Pré-Postagens Selecionadas (${selecionados})`;
  } else {
    btnEmitirLote.textContent = `🚀 Gerar Pré-Postagens Selecionadas`;
  }
}

function atualizarQtdEtiquetasLinha(idx, val) {
  const qtd = Math.max(1, Math.min(20, parseInt(val, 10) || 1));
  if (todosPedidos[idx]) {
    todosPedidos[idx].qtd_etiquetas = qtd;
  }
  const inp = document.getElementById(`qtdEtqRow_${idx}`);
  if (inp && parseInt(inp.value, 10) !== qtd) {
    inp.value = qtd;
  }
}

function renderTabelaPrata(expedicoes) {
  const tableBody = document.getElementById("tableBody");
  if (!tableBody) return;

  let html = "";
  expedicoes.forEach((exp, idx) => {
    const isPedido = exp.tipo_origem === "PEDIDO";
    const badgeBg = isPedido ? "rgba(59, 130, 246, 0.2)" : "rgba(245, 158, 11, 0.2)";
    const badgeColor = isPedido ? "#60a5fa" : "#fbbf24";
    const badgeBorder = isPedido ? "#3b82f6" : "#f59e0b";
    const tipoLabel = isPedido ? "PEDIDO" : "REMESSA";
    
    const numOrigemDisplay = isPedido 
      ? (exp.numero_pedido || (exp.codigo_pedido_omie ? `#${exp.codigo_pedido_omie}` : "S/N"))
      : (exp.numero_remessa || (exp.codigo_remessa_omie ? `#${exp.codigo_remessa_omie}` : "S/N"));

    const transpTag = exp.transportadora_normalizada || "OUTROS";
    const servicoTag = exp.servico_normalizado || "OUTROS";
    const qtdAtual = (todosPedidos[idx] && todosPedidos[idx].qtd_etiquetas) ? todosPedidos[idx].qtd_etiquetas : 1;

    const seletorQtdHtml = `<div style="display: inline-flex; align-items: center; gap: 3px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 6px; padding: 2px 5px;" title="Quantidade de etiquetas / volumes a gerar para esta Nota Fiscal">
           <span style="font-size: 0.7rem; color: #38bdf8; font-weight: 700;">🏷️</span>
           <input type="number" id="qtdEtqRow_${idx}" min="1" max="20" value="${qtdAtual}" onchange="atualizarQtdEtiquetasLinha(${idx}, this.value)" onclick="this.select()" style="width: 38px; text-align: center; background: #0f172a; color: #38bdf8; border: 1px solid #334155; border-radius: 4px; padding: 2px; font-weight: 800; font-size: 0.82rem;">
         </div>`;

    html += `
      <tr>
        <td><input type="checkbox" class="chk-pedido" data-idx="${idx}" onchange="atualizarBotaoEmissao()"></td>
        <td>
          <span style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">
            ${tipoLabel}
          </span>
        </td>
        <td><strong style="color: #f8fafc;">${numOrigemDisplay}</strong></td>
        <td>
          <div><strong style="color: #e2e8f0;">NF ${exp.numero_nf || 'S/N'}</strong></div>
          <div style="font-size: 0.74rem; color: #38bdf8; font-weight: 600; margin-top: 2px;">📅 ${exp.data_emissao || '--/--/----'}</div>
          <small style="color: #64748b; font-size: 0.7rem;">${exp.chave_nfe ? exp.chave_nfe.substring(0, 14) + '...' : ''}</small>
        </td>
        <td>
          <div><strong style="color: #f1f5f9;">${exp.cliente_nome || 'CLIENTE OMIE'}</strong></div>
          <small style="color: #94a3b8; font-size: 0.75rem;">CPF/CNPJ: ${exp.cliente_cpf_cnpj || 'N/I'}</small>
        </td>
        <td>
          <div style="color: #e2e8f0; font-weight: 500;">${exp.cidade || 'N/I'} / ${exp.uf || ''}</div>
          <small style="color: #64748b; font-size: 0.72rem;">${exp.cep ? 'CEP: ' + exp.cep : ''}</small>
        </td>
        <td>
          <div><strong style="color: #38bdf8;">${transpTag}</strong></div>
          <small style="color: #94a3b8; font-size: 0.75rem;">${servicoTag}</small>
        </td>
        <td><strong style="color: #10b981;">R$ ${Number(exp.valor_nf || 0).toFixed(2)}</strong></td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            ${seletorQtdHtml}
            <button class="btn btn-sm btn-primary" onclick="abrirModalEditarPedido(${idx})" title="Visualizar / Editar Endereço e Quantidade de Etiquetas">✏️</button>
            <button class="btn btn-sm btn-success" onclick="emitirUnico(${idx})" title="Gerar Pré-Postagem">🚀</button>
          </div>
        </td>
      </tr>
    `;
  });

  tableBody.innerHTML = html;
  atualizarBotaoEmissao();
  carregarEtiquetasTotalExpress();
}

async function sincronizarComOmie() {
  const btnAtualizarOmie = document.getElementById("btnAtualizarOmie");
  const origText = btnAtualizarOmie ? btnAtualizarOmie.textContent : "";

  if (btnAtualizarOmie) {
    btnAtualizarOmie.disabled = true;
    btnAtualizarOmie.textContent = "⏳ Sincronizando com Omie (Últimos 3 dias)...";
  }

  const periodoAtual = expedicoesPrataState.periodo || "3d";
  let diasParaSincronizar = 3;
  if (periodoAtual === "hoje") diasParaSincronizar = 1;
  else if (periodoAtual === "ontem") diasParaSincronizar = 2;
  else if (periodoAtual === "7d") diasParaSincronizar = 7;
  else if (periodoAtual === "15d") diasParaSincronizar = 15;
  else if (periodoAtual === "30d") diasParaSincronizar = 30;

  try {
    const res = await fetch("/.netlify/functions/omie-sync-bronze-prata", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dias: diasParaSincronizar })
    });

    const data = await safeFetchJson(res);

    if (data.sucesso) {
      const m = data.metricas || {};
      alert(
        `✅ Sincronização Incremental Concluída!

` +
        `• NFs encontradas no Omie: ${m.quantidade_encontrada || 0}
` +
        `• NFs já existentes no Bronze: ${m.quantidade_existente || 0}
` +
        `• Novas NFs baixadas: ${m.quantidade_nova || 0}
` +
        `• Expedições enriquecidas Prata: ${m.quantidade_enriquecida || 0}
` +
        `• Remessas faturadas recentes: ${m.remessas_faturadas_encontradas || 0}
` +
        `• Remessas novas incluídas: ${m.remessas_novas || 0}
` +
        (m.remessas_erros ? `• Falhas ao consultar remessas: ${m.remessas_erros}
` : "") +
        (m.remessas_aviso ? `• Aviso: ${m.remessas_aviso}
` : "") +
        `• ConsultarPedido executados: ${m.consultar_pedido_executados || 0}
` +
        `• ConsultarRemessa executados: ${m.consultar_remessa_executados || 0}
` +
        `• Erros: ${m.quantidade_erro || 0}`
      );
      // Recarregar Turso DB Prata
      await carregarExpedicoesPrata(1);
    } else {
      alert("⚠️ Erro na sincronização com Omie: " + (data.erro || "Erro desconhecido"));
      if ((data.remessas_sync?.novas || 0) > 0) {
        await carregarExpedicoesPrata(1);
        alert(`As notas não concluíram a sincronização, mas ${data.remessas_sync.novas} remessa(s) nova(s) faturada(s) já foram incluídas na lista.`);
      }
    }
  } catch (err) {
    alert("❌ Falha na chamada de sincronização: " + err.message);
  } finally {
    if (btnAtualizarOmie) {
      btnAtualizarOmie.disabled = false;
      btnAtualizarOmie.textContent = origText;
    }
  }
}

// ABA 2: ETIQUETAS GERADAS / REIMPRESSÃO / CANCELAMENTO
function initGeradasTab() {
  const chkAll = document.getElementById("chkSelectAllAguardando");
  if (chkAll) {
    chkAll.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      const checkboxes = document.querySelectorAll("#tableBodyAguardando .chk-gerada");
      checkboxes.forEach(chk => {
        chk.checked = isChecked;
      });
    });
  }

  const tbody = document.getElementById("tableBodyAguardando");
  if (tbody) {
    tbody.addEventListener("change", (e) => {
      if (e.target && e.target.classList.contains("chk-gerada")) {
        const allChks = Array.from(document.querySelectorAll("#tableBodyAguardando .chk-gerada"));
        const allChecked = allChks.length > 0 && allChks.every(c => c.checked);
        const chkAllHeader = document.getElementById("chkSelectAllAguardando");
        if (chkAllHeader) chkAllHeader.checked = allChecked;
      }
    });
  }

  // BOTÃO EXCLUIR / CANCELAR SELECIONADOS
  document.getElementById("btnExcluirEtiquetas").addEventListener("click", async () => {
    const selecionados = Array.from(document.querySelectorAll("#tableBodyAguardando .chk-gerada:checked"));
    if (selecionados.length === 0) {
      alert("Selecione pelo menos uma pré-postagem para cancelar.");
      return;
    }

    const itensParaCancelar = selecionados.map(chk => {
      const idx = parseInt(chk.dataset.idx);
      return { idx, item: etiquetasGeradas[idx] };
    }).filter(x => x.item);

    let msg = `Deseja realmente cancelar ${itensParaCancelar.length} pré-postagens?

`;
    itensParaCancelar.forEach(x => {
      const p = x.item;
      const pedNum = p.dadosPedido?.numero_pedido || p.nf || '-';
      const nfStr = p.nf ? ` / NF ${p.nf}` : '';
      msg += `- Ped #${pedNum}${nfStr} — ${p.servico || '-'}
`;
    });
    msg += `
Esta ação cancelará as pré-postagens selecionadas.`;

    if (!confirm(msg)) return;

    const btn = document.getElementById("btnExcluirEtiquetas");
    const origText = btn ? btn.textContent : "Cancelar Selecionados";
    if (btn) { btn.disabled = true; btn.textContent = "Cancelando..."; }

    let sucessos = 0;
    const falhas = [];
    const indicesRemover = [];

    try {
      for (const x of itensParaCancelar) {
        const res = await executarCancelamentoItem(x.item);
        if (res.sucesso) {
          sucessos++;
          indicesRemover.push(x.idx);
        } else {
          falhas.push({ item: x.item, erro: res.erro });
        }
      }

      // Remover os cancelados de etiquetasGeradas (em ordem decrescente)
      indicesRemover.sort((a, b) => b - a).forEach(i => {
        etiquetasGeradas.splice(i, 1);
      });

      renderEtiquetasGeradas();
      if (typeof carregarDashboardStats === "function") carregarDashboardStats();

      let msgResumo = `Cancelados com sucesso: ${sucessos}
Falharam: ${falhas.length}`;
      if (falhas.length > 0) {
        msgResumo += `

Itens com falha:
` + falhas.map(f => `- ${f.item.objeto || f.item.nf}: ${f.erro}`).join('\n');
      }
      alert(msgResumo);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  });

  // BOTÃO IMPRIMIR SELECIONADOS (RÓTULO + DANFE EM LOTE)
  document.getElementById("btnImprimirSelecionados").addEventListener("click", async () => {
    const selecionados = Array.from(document.querySelectorAll("#tableBodyAguardando .chk-gerada:checked"));
    if (selecionados.length === 0) {
      alert("Selecione pelo menos uma pré-postagem para imprimir os documentos.");
      return;
    }

    const btn = document.getElementById("btnImprimirSelecionados");
    const origText = btn ? btn.textContent : "Imprimir Selecionados";
    if (btn) { btn.disabled = true; btn.textContent = "Unificando Documentos..."; }

    try {
      const { PDFDocument } = PDFLib;
      const pdfFinal = await PDFDocument.create();
      const itensComSucesso = [];

      for (const chk of selecionados) {
        const idx = parseInt(chk.dataset.idx);
        const item = etiquetasGeradas[idx];
        if (!item) continue;

        try {
          // 1. Obter Rótulo
          const rotuloBase64 = await obterPdfRotulo(item, btn);
          if (rotuloBase64) {
            const docRotulo = await PDFDocument.load(rotuloBase64);
            const paginasRotulo = await pdfFinal.copyPages(docRotulo, docRotulo.getPageIndices());
            paginasRotulo.forEach(p => pdfFinal.addPage(p));
          }

          // 2. Obter DANFE Simplificada (ou Declaração)
          const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
          if (danfeBase64) {
            const docDanfe = await PDFDocument.load(danfeBase64);
            const paginasDanfe = await pdfFinal.copyPages(docDanfe, docDanfe.getPageIndices());
            paginasDanfe.forEach(p => pdfFinal.addPage(p));
          }

          itensComSucesso.push(item);
        } catch (errItem) {
          console.error(`Erro ao gerar PDF para ${item.objeto}:`, errItem);
          alert(`Erro ao gerar PDF para Pedido/NF ${item.nf || item.objeto}: ${errItem.message}`);
        }
      }

      if (itensComSucesso.length > 0) {
        // Registrar impressao no Turso (PRONTO -> ARQUIVADO) SOMENTE após geração com sucesso
        for (const item of itensComSucesso) {
          await registrarImpressaoNoTurso(item.idPrePostagem, item.objeto);
          item.statusImpressao = "ARQUIVADO";
        }

        // Remove itens impressos da Aba 2 e recarrega Aba 3
        etiquetasGeradas = etiquetasGeradas.filter(e => !itensComSucesso.includes(e));
        renderEtiquetasGeradas();
        if (typeof carregarArquivoTurso === "function") carregarArquivoTurso();

        const finalBytes = await pdfFinal.save();
        const finalBase64 = base64ArrayBuffer(finalBytes);
        imprimirPdfBase64(finalBase64);
      }
    } catch (err) {
      alert("Erro na unificação em lote: " + err.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  });
}

function renderEtiquetasGeradas() {
  const tbody = document.getElementById("tableBodyAguardando");
  if (!tbody) return;

  if (etiquetasGeradas.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Nenhuma etiqueta para impressão.</td></tr>';
    const chkAll = document.getElementById("chkSelectAllAguardando");
    if (chkAll) chkAll.checked = false;
    return;
  }

  tbody.innerHTML = etiquetasGeradas.map((e, idx) => {
    const pedNum = e.dadosPedido?.numero_pedido || e.nf || '-';
    const nfStr = e.nf ? (' / NF ' + e.nf) : '';
    const pedNfDisplay = 'Ped #' + pedNum + nfStr;
    const temDanfe = Boolean(e.chaveNfe && e.chaveNfe.length === 44);
    const servStr = e.servico || '-';
    const destStr = e.destinatario || '-';
    const cidStr = e.cidadeUf || '-';

    return('<tr>' +
      '<td><input type="checkbox" class="chk-gerada" data-idx="' + idx + '" checked></td>' +
      '<td><strong>' + pedNfDisplay + '</strong></td>' +
      '<td><span class="badge badge-info">' + servStr + '</span></td>' + 
      '<td>' + destStr + '</td>' + 
      '<td>' + cidStr + '</td>' + 
      '<td>' + 
        '<div class="btn-action-group" style="display: flex; gap: 4px; flex-wrap: wrap;">' +
          '<button class="btn btn-secondary" style="padding: 3px 6px; font-size: 0.72rem;" onclick="visualizarDocumentosObjeto(' + idx + ', this)">Visualizar Rótulo</button>' + 
          (temDanfe ? '<button class="btn btn-info" style="padding: 3px 6px; font-size: 0.72rem; background: #0284c7; color: #fff;" onclick="visualizarDanfeObjeto(' + idx + ', this)">DANFE Simplificada</button>' : '<button class="btn btn-secondary" style="padding: 3px 6px; font-size: 0.72rem; opacity: 0.5;" disabled title="Sem Nota Fiscal / Avulso">Sem NF</button>') + 
          '<button class="btn btn-primary" style="padding: 3px 6px; font-size: 0.72rem;" onclick="imprimirDocumentosObjeto(' + idx + ', this)">Imprimir</button>' + 
          '<button class="btn btn-danger" style="padding: 3px 6px; font-size: 0.72rem;" onclick="cancelarPrePostagem(' + idx + ')">Cancelar</button>' + 
        '</div>' + 
      '</td>' + 
    '</tr>');
  }).join('');

  const chkAll = document.getElementById("chkSelectAllAguardando");
  if (chkAll) chkAll.checked = true;
}



// ==========================================================================
// ABA 3: ETIQUETAS REIMPRESSÃO (ARQUIVO DE IMPRESSOS)
// ==========================================================================

let etiquetasArquivo = [];
let etiquetasArquivoFiltrados = [];

function initArquivoTab() {
  const chkAll = document.getElementById("chkSelectAllArquivo");
  if (chkAll) {
    chkAll.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      const checkboxes = document.querySelectorAll("#tableBodyArquivo .chk-arquivo");
      checkboxes.forEach(chk => {
        chk.checked = isChecked;
      });
    });
  }

  const tbody = document.getElementById("tableBodyArquivo");
  if (tbody) {
    tbody.addEventListener("change", (e) => {
      if (e.target && e.target.classList.contains("chk-arquivo")) {
        const allChks = Array.from(document.querySelectorAll("#tableBodyArquivo .chk-arquivo"));
        const allChecked = allChks.length > 0 && allChks.every(c => c.checked);
        const chkAllHeader = document.getElementById("chkSelectAllArquivo");
        if (chkAllHeader) chkAllHeader.checked = allChecked;
      }
    });
  }

  const btnFiltrar = document.getElementById("btnFiltrarArquivo");
  if (btnFiltrar) {
    btnFiltrar.addEventListener("click", aplicarFiltrosArquivo);
  }

  const inputBusca = document.getElementById("filterArqBusca");
  if (inputBusca) {
    inputBusca.addEventListener("input", aplicarFiltrosArquivo);
  }

  const selServico = document.getElementById("filterArqServico");
  if (selServico) {
    selServico.addEventListener("change", aplicarFiltrosArquivo);
  }

  const inputDtInicio = document.getElementById("filterArqDataInicio");
  const inputDtFim = document.getElementById("filterArqDataFim");
  if (inputDtInicio) inputDtInicio.addEventListener("change", aplicarFiltrosArquivo);
  if (inputDtFim) inputDtFim.addEventListener("change", aplicarFiltrosArquivo);

  const btnReimprimirSel = document.getElementById("btnReimprimirSelecionados");
  if (btnReimprimirSel) {
    btnReimprimirSel.addEventListener("click", async () => {
      const selecionados = Array.from(document.querySelectorAll("#tableBodyArquivo .chk-arquivo:checked"));
      if (selecionados.length === 0) {
        alert("Selecione pelo menos uma pré-postagem para reimprimir.");
        return;
      }

      const origText = btnReimprimirSel.textContent;
      btnReimprimirSel.disabled = true;
      btnReimprimirSel.textContent = "⏳ Unificando Reimpressões...";

      try {
        const { PDFDocument } = PDFLib;
        const pdfFinal = await PDFDocument.create();
        let gerouAlgum = false;

        for (const chk of selecionados) {
          const idx = parseInt(chk.dataset.idx);
          const item = etiquetasArquivoFiltrados[idx];
          if (!item) continue;

          try {
            const rotuloBase64 = await obterPdfRotulo(item, btnReimprimirSel);
            if (rotuloBase64) {
              const docRotulo = await PDFDocument.load(rotuloBase64);
              const paginasRotulo = await pdfFinal.copyPages(docRotulo, docRotulo.getPageIndices());
              paginasRotulo.forEach(p => pdfFinal.addPage(p));
            }

            const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
            if (danfeBase64) {
              const docDanfe = await PDFDocument.load(danfeBase64);
              const paginasDanfe = await pdfFinal.copyPages(docDanfe, docDanfe.getPageIndices());
              paginasDanfe.forEach(p => pdfFinal.addPage(p));
            }

            gerouAlgum = true;
          } catch (errItem) {
            console.error(`Erro ao reimprimir item ${item.objeto}:`, errItem);
          }
        }

        if (gerouAlgum) {
          const finalBytes = await pdfFinal.save();
          const finalBase64 = base64ArrayBuffer(finalBytes);
          imprimirPdfBase64(finalBase64);
        }
      } catch (err) {
        alert("Erro na reimpressão em lote: " + err.message);
      } finally {
        btnReimprimirSel.disabled = false;
        btnReimprimirSel.textContent = origText;
      }
    });
  }
}

async function carregarArquivoTurso() {
  try {
    const res = await fetch("/.netlify/functions/turso-db?action=list_prepostagens");
    const data = await safeFetchJson(res);
    if (!res.ok || data.ok === false || data.error) {
      console.error("Erro ao carregar arquivo Turso:", data);
      const tbody = document.getElementById("tableBodyArquivo");
      if (tbody) {
        const errMsg = data.error || data.message || `Status HTTP ${res.status}`;
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: #f87171;">
          ⚠️ Erro ao consultar arquivo no Turso DB: <strong>${errMsg}</strong><br>
          <small style="color: #94a3b8;">Verifique se as variáveis <code>CORREIOS_TURSO_URL</code> e <code>CORREIOS_TURSO_TOKEN</code> estão configuradas na Vercel (Project Settings &rarr; Environment Variables) com o banco gestoretiquetas.</small>
        </td></tr>`;
      }
      return;
    }
    if (data.prepostagens && data.prepostagens.length > 0) {
      etiquetasArquivo = data.prepostagens.filter(p => {
        const estaCancelado = p.cancelado === 1 || p.cancelado === "1" || p.cancelado === true || p.status_cancelamento === "CANCELADO";
        const statusImp = (p.status_impressao || "").toUpperCase();
        return (statusImp === "ARQUIVADO" || statusImp === "IMPRESSO") && !estaCancelado;
      }).map(p => ({
        idPrePostagem: p.id_prepostagem,
        objeto: p.codigo_objeto || `OBJ_${p.id}`,
        servico: p.servico,
        destinatario: p.destinatario,
        cidadeUf: `${p.cidade || ''}/${p.uf || ''}`,
        nf: p.numero_nf,
        chaveNfe: p.chave_nfe || "",
        createdAt: p.created_at || "",
        idRecibo: p.id_recibo_atual,
        statusRotulo: p.status_rotulo || "PENDENTE",
        statusImpressao: p.status_impressao || "IMPRESSO",
        obs_entrega: p.obs_entrega || "",
        dadosPedido: {
          numero_pedido: p.pedido,
          numero_nf: p.numero_nf,
          chave_nfe: p.chave_nfe,
          forma_envio: p.servico,
          obs_entrega: p.obs_entrega || "",
          destinatario: {
            nome: p.destinatario,
            cpfCnpj: p.cpf_cnpj_destinatario,
            endereco: {
              logradouro: p.logradouro,
              numero: p.numero,
              complemento: p.complemento || "",
              bairro: p.bairro || "",
              cidade: p.cidade,
              uf: p.uf,
              cep: p.cep
            }
          }
        }
      }));
    } else {
      etiquetasArquivo = [];
    }
    aplicarFiltrosArquivo();
  } catch (err) {
    console.error("Erro ao carregar arquivo de reimpressão do Turso:", err);
  }
}

function aplicarFiltrosArquivo() {
  const busca = (document.getElementById("filterArqBusca")?.value || "").toLowerCase().trim();
  const servicoSel = document.getElementById("filterArqServico")?.value || "TODOS";
  const dtInicioStr = document.getElementById("filterArqDataInicio")?.value || "";
  const dtFimStr = document.getElementById("filterArqDataFim")?.value || "";

  etiquetasArquivoFiltrados = etiquetasArquivo.filter(item => {
    // Filtro Texto
    if (busca) {
      const ped = String(item.dadosPedido?.numero_pedido || "").toLowerCase();
      const nf = String(item.nf || "").toLowerCase();
      const dest = String(item.destinatario || "").toLowerCase();
      const obj = String(item.objeto || "").toLowerCase();
      if (!ped.includes(busca) && !nf.includes(busca) && !dest.includes(busca) && !obj.includes(busca)) {
        return false;
      }
    }

    // Filtro Servico
    if (servicoSel !== "TODOS") {
      const s = (item.servico || "").toUpperCase();
      if (servicoSel === "IMPRESSO_MODICO" && !s.includes("MODICO")) return false;
      if (servicoSel === "PAC" && !s.includes("PAC")) return false;
      if (servicoSel === "SEDEX" && !s.includes("SEDEX")) return false;
      if (servicoSel === "MINI ENVIOS" && !s.includes("MINI")) return false;
    }

    // Filtro Data
    if (dtInicioStr && item.createdAt) {
      const dtItem = new Date(item.createdAt);
      const dtIni = new Date(dtInicioStr + "T00:00:00");
      if (dtItem < dtIni) return false;
    }
    if (dtFimStr && item.createdAt) {
      const dtItem = new Date(item.createdAt);
      const dtFim = new Date(dtFimStr + "T23:59:59");
      if (dtItem > dtFim) return false;
    }

    return true;
  });

  renderEtiquetasArquivo(etiquetasArquivoFiltrados);
}

function renderEtiquetasArquivo(lista) {
  const tbody = document.getElementById("tableBodyArquivo");
  const countSpan = document.getElementById("totalCountArquivo");
  if (countSpan) countSpan.textContent = lista.length;

  if (!tbody) return;

  if (lista.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Nenhuma etiqueta no arquivo de reimpressão.</td></tr>';
    const chkAll = document.getElementById("chkSelectAllArquivo");
    if (chkAll) chkAll.checked = false;
    return;
  }

  tbody.innerHTML = lista.map((e, idx) => {
    const pedNum = e.dadosPedido?.numero_pedido || e.nf || '-';
    const nfStr = e.nf ? (' / NF ' + e.nf) : '';
    const pedNfDisplay = 'Ped #' + pedNum + nfStr;
    const temDanfe = Boolean(e.chaveNfe && e.chaveNfe.length === 44);
    const servStr = e.servico || '-';
    const destStr = e.destinatario || '-';

    return('<tr>' +
      '<td><input type="checkbox" class="chk-arquivo" data-idx="' + idx + '" checked></td>' +
      '<td><strong>' + pedNfDisplay + '</strong></td>' +
      '<td><span class="badge badge-info">' + servStr + '</span></td>' +
      '<td>' + destStr + '</td>' +
      '<td><span class="badge badge-secondary">Não gerada</span></td>' +
      '<td>' +
        '<div class="btn-action-group" style="display: flex; gap: 4px; flex-wrap: wrap;">' +
          '<button class="btn btn-secondary" style="padding: 3px 6px; font-size: 0.72rem;" onclick="visualizarDocumentosObjetoArquivo(' + idx + ', this)">Visualizar Rótulo</button>' +
          '<button class="btn btn-info" style="padding: 3px 6px; font-size: 0.72rem; background: #0284c7; color: #fff;" onclick="visualizarDanfeObjetoArquivo(' + idx + ', this)">DANFE Simplificada</button>' +
          '<button class="btn btn-primary" style="padding: 3px 6px; font-size: 0.72rem;" onclick="reimprimirDocumentosObjetoArquivo(' + idx + ', this)">Reimprimir</button>' +
          '<button class="btn btn-danger" style="padding: 3px 6px; font-size: 0.72rem;" onclick="cancelarPrePostagemArquivo(' + idx + ')">Cancelar</button>' +
        '</div>' +
      '</td>' +
    '</tr>');
  }).join('');

  const chkAll = document.getElementById("chkSelectAllArquivo");
  if (chkAll) chkAll.checked = true;
}

async function visualizarDocumentosObjetoArquivo(idx, btnElement = null) {
  const item = etiquetasArquivoFiltrados[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const rotuloBase64 = await obterPdfRotulo(item, btnElement);
    await visualizarPdfBase64(rotuloBase64);
  } catch (err) {
    alert(`[ERRO_ABERTURA_PDF]: ${err.message}`);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}

async function visualizarDanfeObjetoArquivo(idx, btnElement = null) {
  const item = etiquetasArquivoFiltrados[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
    const blob = base64ToBlob(danfeBase64, "application/pdf");
    const blobUrl = URL.createObjectURL(blob);
    const win = window.open(blobUrl, "_blank");
    if (win) {
      win.focus();
    } else {
      alert("Bloqueador de pop-ups impediu a abertura do documento fiscal. Por favor, libere os pop-ups.");
    }
  } catch (err) {
    alert(err.message);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}

async function reimprimirDocumentosObjetoArquivo(idx, btnElement = null) {
  const item = etiquetasArquivoFiltrados[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const rotuloBase64 = await obterPdfRotulo(item, btnElement);
    const { PDFDocument } = PDFLib;
    const pdfItem = await PDFDocument.create();

    let jaContemDanfe = false;
    if (rotuloBase64) {
      const docRotulo = await PDFDocument.load(rotuloBase64);
      if (docRotulo.getPageCount() > 1) {
        jaContemDanfe = true;
      }
      const paginasRotulo = await pdfItem.copyPages(docRotulo, docRotulo.getPageIndices());
      paginasRotulo.forEach(p => pdfItem.addPage(p));
    }

    if (!jaContemDanfe) {
      const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
      if (danfeBase64) {
        const docDanfe = await PDFDocument.load(danfeBase64);
        const paginasDanfe = await pdfItem.copyPages(docDanfe, docDanfe.getPageIndices());
        paginasDanfe.forEach(p => pdfItem.addPage(p));
      }
    }

    const finalBytes = await pdfItem.save();
    const finalBase64 = base64ArrayBuffer(finalBytes);

    imprimirPdfBase64(finalBase64);
  } catch (err) {
    alert(`[ERRO_REIMPRESSAO]: ${err.message}`);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}



// ==========================================================================
// OBTENÇÃO E VISUALIZAÇÃO DE RÓTULOS E DOCUMENTOS
// ==========================================================================

function visualizarPdfBase64(pdfBase64) {
  if (!pdfBase64) return;
  const blob = base64ToBlob(pdfBase64, "application/pdf");
  const blobUrl = URL.createObjectURL(blob);
  const win = window.open(blobUrl, "_blank");
  if (win) {
    win.focus();
  } else {
    alert("Bloqueador de pop-ups impediu a abertura do documento. Por favor, libere os pop-ups.");
  }
}

async function obterPdfRotulo(item, btnElement = null) {
  if (!item) return null;

  // 1. Se ja houver pdfBase64 em memoria no item
  if (item.pdfBase64) {
    return item.pdfBase64;
  }

  const serv = (item.servico || "").toUpperCase();
  const idPre = item.idPrePostagem || item.id_prepostagem || "";
  if (serv === "RETIRADA_GUARITA" || serv === "RETIRADA_ESTOQUE") {
    const pdfB64 = await gerarRotuloRetiradaLocalPdf(item);
    item.pdfBase64 = pdfB64;
    return pdfB64;
  }
  const isTotalExpress = serv.includes("TOTAL") || serv === "EXP" || serv === "STD" || idPre.startsWith("TOTAL_EXPRESS_") || (item.objeto && item.objeto.toUpperCase().startsWith("TX"));
  if (isTotalExpress) {
    const awb = item.objeto || idPre.replace("TOTAL_EXPRESS_", "");
    try {
      const resTot = await fetch("/.netlify/functions/total-express?action=etiqueta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ awb: awb, pedido: item.dadosPedido || item })
      });
      const dataTot = await safeFetchJson(resTot);
      if (dataTot && dataTot.pdfBase64) {
        item.pdfBase64 = dataTot.pdfBase64;
        return dataTot.pdfBase64;
      }
      throw new Error(dataTot?.erro || "Não foi possível carregar a etiqueta oficial da Total Express.");
    } catch (eTot) {
      console.error("Falha ao obter rótulo Total Express:", eTot);
      throw eTot;
    }
  }

  const isSouza = serv.includes("SOUZA") || serv.includes("ENTREGA_PROPRIA") || serv.includes("LOCAL") || (item.objeto && item.objeto.startsWith("SZ")) || idPre.startsWith("SOUZA_");
  const isModico = serv.includes("MODICO") || serv.includes("20133") || (item.objeto && item.objeto.startsWith("YD")) || idPre.startsWith("MODICO_");

  // Rótulo Dedicado Souza / Entrega Própria (Fortaleza e RMF)
  if (isSouza) {
    const pdfB64 = await gerarRotuloSouzaLocalPdf(item);
    item.pdfBase64 = pdfB64;
    return pdfB64;
  }

  // 2. Se for Impresso Modico ou idPre local -> usar gerador padronizado interno
  if (isModico || !idPre || idPre.startsWith("MODICO_") || idPre.startsWith("ID_")) {
    const pdfB64 = await gerarRotuloPadronizadoInternoPdf(item, isModico ? "MODICO" : null);
    item.pdfBase64 = pdfB64;
    return pdfB64;
  }

  // 3. Se for CWS PAC/SEDEX/MINI com idPrePostagem -> consultar endpoint correios-rotulo
  try {
    const resRot = await fetch("/.netlify/functions/correios-rotulo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        idsPrePostagem: [idPre],
        tipoRotulo: "P",
        formatoRotulo: "ET"
      })
    });
    const dataRot = await safeFetchJson(resRot);
    if (dataRot && dataRot.pdfBase64) {
      item.pdfBase64 = dataRot.pdfBase64;
      return dataRot.pdfBase64;
    }
  } catch (errCws) {
    console.warn("Falha ao obter rotulo CWS, usando gerador padronizado interno:", errCws);
  }

  // Fallback: Gerador padronizado interno
  const pdfFallback = await gerarRotuloPadronizadoInternoPdf(item);
  item.pdfBase64 = pdfFallback;
  return pdfFallback;
}

async function visualizarDocumentosObjeto(idx, btnElement = null) {
  const item = etiquetasGeradas[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const rotuloBase64 = await obterPdfRotulo(item, btnElement);
    visualizarPdfBase64(rotuloBase64);
  } catch (err) {
    alert(`[ERRO_ABERTURA_PDF]: ${err.message}`);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}

async function visualizarDanfeObjeto(idx, btnElement = null) {
  const item = etiquetasGeradas[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
    visualizarPdfBase64(danfeBase64);
  } catch (err) {
    alert(err.message);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}



// ==========================================================================
// HELPERS CONVERSÃO E NAVEGAÇÃO DE PDF (BASE64 / BLOB / TURSO / FISCAL)
// ==========================================================================

function base64ArrayBuffer(arrayBuffer) {
  let binary = "";
  const bytes = new Uint8Array(arrayBuffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

function base64ToBlob(base64, type = "application/pdf") {
  const binStr = window.atob(base64);
  const len = binStr.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binStr.charCodeAt(i);
  }
  return new Blob([bytes], { type });
}

function imprimirPdfBase64(pdfBase64) {
  if (!pdfBase64) return;
  const blob = base64ToBlob(pdfBase64, "application/pdf");
  const blobUrl = URL.createObjectURL(blob);
  const win = window.open(blobUrl, "_blank");
  if (win) {
    win.focus();
  } else {
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = `documento_${Date.now()}.pdf`;
    link.click();
  }
}

async function registrarImpressaoNoTurso(idPrePostagem, codigoObjeto) {
  try {
    await fetch("/.netlify/functions/turso-db?action=register_impressao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_prepostagem: idPrePostagem || "",
        codigo_objeto: codigoObjeto || "",
        usuario_impressao: "OPERADOR"
      })
    });
  } catch (err) {
    console.error("Erro ao registrar status de impressão no Turso:", err);
  }
}

function extrairDadosFiscaisReais(item) {
  const ped = item.dadosPedido || {};
  const chaveNfe = item.chaveNfe || ped.chave_nfe || "";
  const nf = item.nf || ped.numero_nf || "";
  const temChaveReal = Boolean(chaveNfe && chaveNfe.length === 44);

  return {
    temChaveReal,
    chaveNfe,
    nf,
    origemChave: temChaveReal ? "DADOS_NFE" : "AUSENTE",
    valorTotal: ped.valor_total !== undefined ? ped.valor_total : null,
    protocolo: ped.protocolo || null,
    dataEmissao: ped.data_emissao || null,
    dataAutorizacao: ped.data_autorizacao || null,
    emitente: ped.emitente || null,
    destinatario: ped.destinatario || null
  };
}

async function obterPdfDanfeOuDeclaracao(item) {
  if (!item) return null;
  const fiscal = extrairDadosFiscaisReais(item);

  if (fiscal.temChaveReal) {
    const ped = item.dadosPedido || {};
    const emit = fiscal.emitente || {
      nome: "COMUNIDADE CATOLICA SHALOM",
      cnpj: "07.044.456/0003-64",
      ie: "068937741",
      logradouro: "RUA BERRA BODE - JAMBREIRO",
      numero: "S/N",
      bairro: "BERRA BODE",
      cidade: "Aquiraz",
      uf: "CE",
      cep: "61700-000"
    };

    const dest = fiscal.destinatario || {
      nome: item.destinatario || "Cliente",
      cpfCnpj: ped.destinatario?.cpfCnpj || ped.cpf_cnpj_destinatario || "00000000000",
      logradouro: ped.destinatario?.endereco?.logradouro || ped.logradouro || "Rua",
      numero: ped.destinatario?.endereco?.numero || ped.numero || "S/N",
      cidade: ped.destinatario?.endereco?.cidade || ped.cidade || "Aquiraz",
      uf: ped.destinatario?.endereco?.uf || ped.uf || "CE",
      cep: ped.destinatario?.endereco?.cep || ped.cep || "61700-000"
    };

    const payloadDanfe = {
      chaveNfe: fiscal.chaveNfe,
      nNF: String(fiscal.nf),
      serie: "1",
      dhEmi: fiscal.dataEmissao || new Date().toLocaleString(),
      nProt: fiscal.protocolo || null,
      dhRecbto: fiscal.dataAutorizacao || null,
      tpNF: "1",
      vNF: fiscal.valorTotal !== null ? fiscal.valorTotal : 0.00,
      emitente: emit,
      destinatario: dest
    };

    const resDanfe = await fetch("/.netlify/functions/danfe-simplificada", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ danfe: payloadDanfe })
    });

    const dataDanfe = await safeFetchJson(resDanfe);
    if (dataDanfe && dataDanfe.pdfBase64) return dataDanfe.pdfBase64;
    throw new Error(dataDanfe?.error || "Erro ao gerar DANFE Simplificada");
  }

  // Se for entrega avulsa (SEM_NF) ou serviço sem nota fiscal, não lançar erro impeditivo de DANFE
  const pedInfo = item.dadosPedido || {};
  const isAvulso = item.tipo_item === "AVULSO" || pedInfo.tipo_item === "AVULSO" || fiscal.nf === "SEM_NF" || item.pedido === "AVULSO" || item.nf === "SEM_NF";
  if (isAvulso || !fiscal.nf || fiscal.nf === "-" || fiscal.nf === "0") {
    return null;
  }

  // Se for Souza / Entrega Própria sem chave autorizada, também não impede impressão do rótulo
  const servUpper = (item.servico || "").toUpperCase();
  if (servUpper.includes("SOUZA") || servUpper.includes("ENTREGA_PROPRIA") || (item.objeto && item.objeto.startsWith("SZ"))) {
    return null;
  }

  if (fiscal.nf && fiscal.nf !== "-" && fiscal.nf !== "0") {
    throw new Error(`[CHAVE_NFE_AUSENTE] Não é possível gerar DANFE Simplificada para a NF ${fiscal.nf} pois a Chave NF-e está ausente.`);
  }

  // Declaração de Conteúdo fallback
  const { PDFDocument, StandardFonts } = PDFLib;
  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([595.28, 841.89]);
  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  page.drawText("DECLARAÇÃO DE CONTEÚDO", { x: 180, y: 800, size: 14, font: fontBold });
  page.drawText(`Destinatário: ${item.destinatario || "-"}`, { x: 50, y: 760, size: 10, font: fontReg });
  page.drawText(`Cidade/UF: ${item.cidadeUf || "-"}`, { x: 50, y: 740, size: 10, font: fontReg });

  const bytes = await pdfDoc.save();
  return base64ArrayBuffer(bytes);
}

async function imprimirDocumentosObjeto(idx, btnElement = null) {
  const item = etiquetasGeradas[idx];
  if (!item) return;

  const btnOriginal = btnElement ? btnElement.textContent : "";
  if (btnElement) { btnElement.disabled = true; btnElement.textContent = "⌛ Processando..."; }

  try {
    const rotuloBase64 = await obterPdfRotulo(item, btnElement);
    const { PDFDocument } = PDFLib;
    const pdfItem = await PDFDocument.create();

    let jaContemDanfe = false;
    if (rotuloBase64) {
      const docRotulo = await PDFDocument.load(rotuloBase64);
      if (docRotulo.getPageCount() > 1) {
        jaContemDanfe = true;
      }
      const paginasRotulo = await pdfItem.copyPages(docRotulo, docRotulo.getPageIndices());
      paginasRotulo.forEach(p => pdfItem.addPage(p));
    }

    if (!jaContemDanfe) {
      const danfeBase64 = await obterPdfDanfeOuDeclaracao(item);
      if (danfeBase64) {
        const docDanfe = await PDFDocument.load(danfeBase64);
        const paginasDanfe = await pdfItem.copyPages(docDanfe, docDanfe.getPageIndices());
        paginasDanfe.forEach(p => pdfItem.addPage(p));
      }
    }

    const finalBytes = await pdfItem.save();
    const finalBase64 = base64ArrayBuffer(finalBytes);

    await registrarImpressaoNoTurso(item.idPrePostagem, item.objeto);
    item.statusImpressao = "ARQUIVADO";
    etiquetasGeradas.splice(idx, 1);
    renderEtiquetasGeradas();
    if (typeof carregarArquivoTurso === "function") carregarArquivoTurso();

    imprimirPdfBase64(finalBase64);
  } catch (err) {
    alert(`[ERRO_GERACAO_PDF]: ${err.message}`);
  } finally {
    if (btnElement) { btnElement.disabled = false; btnElement.textContent = btnOriginal; }
  }
}


// ==================================================
// ABA 4: HISTÓRICO DE PRÉ-POSTAGENS & PORTAL POSTAL
// ==================================================
let dadosRastreioPortalCache = [];

function setRastreioAtalhoData(opcao) {
  const iniInput = document.getElementById("rastreioDataInicio");
  const fimInput = document.getElementById("rastreioDataFim");
  if (!iniInput || !fimInput) return;

  const hoje = new Date();
  const fmt = d => d.toISOString().split("T")[0];

  fimInput.value = fmt(hoje);

  if (opcao === "hoje") {
    iniInput.value = fmt(hoje);
  } else if (opcao === "7dias") {
    const d = new Date(hoje.getTime() - 7 * 24 * 60 * 60 * 1000);
    iniInput.value = fmt(d);
  } else if (opcao === "15dias") {
    const d = new Date(hoje.getTime() - 15 * 24 * 60 * 60 * 1000);
    iniInput.value = fmt(d);
  } else if (opcao === "30dias") {
    const d = new Date(hoje.getTime() - 30 * 24 * 60 * 60 * 1000);
    iniInput.value = fmt(d);
  }
}

async function consultarPortalPostalIndependente() {
  const btn = document.getElementById("btnConsultarPortalPostal");
  const tbody = document.getElementById("tableBodyRastreamentoPortal");
  const dIni = document.getElementById("rastreioDataInicio")?.value || "";
  const dFim = document.getElementById("rastreioDataFim")?.value || "";
  const sro = document.getElementById("rastreioBuscaSro")?.value || "";

  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Consultando Portal Postal...";
  }

  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Consultando serviço Portal Postal...</td></tr>`;
  }

  try {
    const params = new URLSearchParams();
    params.append("action", "consultar_periodo");
    if (sro.trim()) {
      params.append("sro", sro.trim());
    } else {
      if (dIni) params.append("data_inicio", dIni);
      if (dFim) params.append("data_fim", dFim);
    }

    const res = await fetch(`/.netlify/functions/portalpostal-rastreio?${params.toString()}`);
    const data = await safeFetchJson(res);

    if (!data.sucesso) {
      throw new Error(data.erro || data.error || "Erro ao consultar Portal Postal");
    }

    dadosRastreioPortalCache = data.registros || [];
    renderTabelaRastreioPortal(dadosRastreioPortalCache);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="10" class="empty-state" style="color: #ef4444;">❌ ${err.message}</td></tr>`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🔍 Consultar Portal Postal";
    }
  }
}

function renderTabelaRastreioPortal(lista) {
  const tbody = document.getElementById("tableBodyRastreamentoPortal");
  const countTotal = document.getElementById("totalCountRastreioPortal");
  const countGestor = document.getElementById("countRastreioGestor");
  const countExternos = document.getElementById("countRastreioExternos");

  if (!tbody) return;

  if (!lista || lista.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Nenhum registro retornado pelo Portal Postal.</td></tr>`;
    if (countTotal) countTotal.textContent = "0";
    if (countGestor) countGestor.textContent = "0";
    if (countExternos) countExternos.textContent = "0";
    return;
  }

  let totalG = 0;
  let totalE = 0;

  const htmlRows = lista.map(r => {
    const isGestor = r.origem === "GESTOR";
    if (isGestor) totalG++; else totalE++;

    const badgeOrigem = isGestor
      ? `<span class="badge badge-success">GESTOR</span>`
      : `<span class="badge badge-primary">PORTAL POSTAL</span>`;

    const sroCell = r.sro
      ? `<a href="javascript:void(0)" class="sro-tracker-link" onclick="abrirModalRastreioSro('${r.sro}')" title="Clique para ver rastreamento completo SRO Rastro">🔍 <strong>${r.sro}</strong></a>`
      : "-";

    return `
      <tr>
        <td>${r.data_postagem || "-"}</td>
        <td>${sroCell}</td>
        <td>${r.nf || "-"}</td>
        <td>${r.servico || "-"}</td>
        <td>${r.destinatario || "-"}</td>
        <td>${r.cep || "-"}</td>
        <td>${r.situacao || "-"}</td>
        <td>${r.data_situacao || "-"}</td>
        <td>${r.data_prazo || "-"}</td>
        <td>${badgeOrigem}</td>
      </tr>
    `;
  }).join("");

  tbody.innerHTML = htmlRows;
  if (countTotal) countTotal.textContent = String(lista.length);
  if (countGestor) countGestor.textContent = String(totalG);
  if (countExternos) countExternos.textContent = String(totalE);
}

function filtrarTabelaRastreioLocal() {
  const texto = (document.getElementById("filterRastreioTexto")?.value || "").toLowerCase();
  const servico = document.getElementById("filterRastreioServico")?.value || "TODOS";
  const origem = document.getElementById("filterRastreioOrigem")?.value || "TODOS";

  const filtrados = dadosRastreioPortalCache.filter(r => {
    const matchTexto = !texto ||
      (r.sro && r.sro.toLowerCase().includes(texto)) ||
      (r.nf && r.nf.toLowerCase().includes(texto)) ||
      (r.destinatario && r.destinatario.toLowerCase().includes(texto));

    const matchServico = servico === "TODOS" || (r.servico && r.servico.toUpperCase().includes(servico));
    const matchOrigem = origem === "TODOS" || r.origem === origem;

    return matchTexto && matchServico && matchOrigem;
  });

  renderTabelaRastreioPortal(filtrados);
}


// ==================================================
// MODAL DE RASTREAMENTO SRO RASTRO (ABA 4)
// ==================================================
async function abrirModalRastreioSro(sroCode) {
  if (!sroCode) return;

  const modal = document.getElementById("modalRastreioSro");
  const codeText = document.getElementById("modalSroCodigoText");
  const timeline = document.getElementById("modalSroTimeline");
  const statusBadge = document.getElementById("modalSroStatusBadge");
  const previsao = document.getElementById("modalSroPrevisao");
  const ultimaAtt = document.getElementById("modalSroUltimaAtualizacao");
  const contratoServico = document.getElementById("modalSroContratoServico");
  const tipoBadge = document.getElementById("modalSroTipoPostalBadge");

  if (!modal) return;

  modal.style.display = "flex";
  if (codeText) codeText.textContent = sroCode;
  if (previsao) previsao.textContent = "Carregando...";
  if (ultimaAtt) ultimaAtt.textContent = "Carregando...";
  if (contratoServico) contratoServico.textContent = "Carregando...";
  if (statusBadge) {
    statusBadge.textContent = "Consultando...";
    statusBadge.className = "badge badge-primary";
  }

  if (timeline) {
    timeline.innerHTML = `
      <div style="text-align: center; padding: 30px; color: #94a3b8;">
        ⏳ Consultando API SRO Rastro oficial para <strong>${sroCode}</strong>...
      </div>
    `;
  }

  try {
    const res = await fetch(`/.netlify/functions/sro-rastro-consulta?codigoObjeto=${encodeURIComponent(sroCode)}`);
    const data = await safeFetchJson(res);

    if (!data.sucesso) {
      throw new Error(data.erro || "Não foi possível carregar as informações do SRO Rastro.");
    }

    // Preencher Resumo Superior
    if (previsao) {
      if (data.previsaoEntrega) {
        const d = new Date(data.previsaoEntrega);
        previsao.textContent = isNaN(d.getTime()) ? data.previsaoEntrega : d.toLocaleDateString("pt-BR");
      } else {
        previsao.textContent = "Não informada";
      }
    }

    if (contratoServico) {
      const tpDesc = data.tipoPostal?.descricao || data.tipoPostal?.categoria || data.modalidade || "";
      const cont = data.contrato ? ` (Contrato ${data.contrato})` : "";
      contratoServico.textContent = (tpDesc + cont).trim() || "Padrão";
    }

    if (tipoBadge) {
      tipoBadge.textContent = data.tipoPostal?.categoria || data.tipoPostal?.sigla || "SRO";
    }

    const ultEv = data.ultimoEvento;

    if (ultimaAtt && ultEv) {
      if (ultEv.dataHora) {
        const d = new Date(ultEv.dataHora);
        ultimaAtt.textContent = isNaN(d.getTime()) ? ultEv.dataHora : `${d.toLocaleDateString("pt-BR")} às ${d.toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' })}`;
      } else {
        ultimaAtt.textContent = "-";
      }
    }

    if (statusBadge && ultEv) {
      statusBadge.textContent = ultEv.descricao || "Status indisponível";
      const codUpper = (ultEv.codigo || "").toUpperCase();
      if (codUpper === "BDE" || ultEv.descricao.toLowerCase().includes("entregue")) {
        statusBadge.className = "badge badge-success";
      } else if (codUpper === "OEC" || ultEv.descricao.toLowerCase().includes("saiu para entrega")) {
        statusBadge.className = "badge badge-info";
      } else if (codUpper === "DO" || codUpper === "RO" || ultEv.descricao.toLowerCase().includes("transferência")) {
        statusBadge.className = "badge badge-primary";
      } else if (codUpper === "PO" || ultEv.descricao.toLowerCase().includes("postado")) {
        statusBadge.className = "badge badge-warning";
      } else {
        statusBadge.className = "badge badge-secondary";
      }
    }

    // Renderizar Timeline dos Eventos
    const eventos = data.eventos || [];
    if (!timeline) return;

    if (eventos.length === 0) {
      timeline.innerHTML = `
        <div style="text-align: center; padding: 30px; color: #94a3b8;">
          Nenhum evento registrado até o momento para este objeto.
        </div>
      `;
      return;
    }

    const timelineHtml = eventos.map(ev => {
      const codUpper = (ev.codigo || "").toUpperCase();
      let nodeClass = "";
      if (codUpper === "BDE" || ev.descricao.toLowerCase().includes("entregue")) nodeClass = "status-entregue";
      else if (codUpper === "OEC" || ev.descricao.toLowerCase().includes("saiu para entrega")) nodeClass = "status-saiu";
      else if (codUpper === "DO" || codUpper === "RO" || ev.descricao.toLowerCase().includes("transferência")) nodeClass = "status-transito";
      else if (codUpper === "PO" || ev.descricao.toLowerCase().includes("postado")) nodeClass = "status-postado";

      let dataFmt = ev.dataHora;
      if (ev.dataHora) {
        const d = new Date(ev.dataHora);
        if (!isNaN(d.getTime())) {
          dataFmt = `${d.toLocaleDateString("pt-BR")} às ${d.toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' })}`;
        }
      }

      const localStr = [ev.unidadeNome || ev.unidadeTipo, ev.unidadeCidadeUF].filter(Boolean).join(" - ");

      let destHtml = "";
      if (ev.unidadeDestino) {
        const destLocal = [ev.unidadeDestino.nome || ev.unidadeDestino.tipo, ev.unidadeDestino.cidade && `${ev.unidadeDestino.cidade}/${ev.unidadeDestino.uf}`].filter(Boolean).join(" - ");
        destHtml = `<div class="sro-timeline-dest">➡️ Em transferência para: <strong>${destLocal}</strong></div>`;
      }

      const detalheText = ev.detalhe || ev.comentario || "";

      return `
        <div class="sro-timeline-node ${nodeClass}">
          <div class="sro-timeline-card">
            <div class="sro-timeline-header">
              <span>📅 ${dataFmt || "-"}</span>
              <span>📍 ${localStr || "Brasil"}</span>
            </div>
            <div class="sro-timeline-desc">
              <span class="badge badge-secondary" style="font-size: 0.7rem; margin-right: 6px;">${ev.codigo}</span>
              ${ev.descricao}
            </div>
            ${detalheText ? `<div class="sro-timeline-detail">${detalheText}</div>` : ""}
            ${destHtml}
          </div>
        </div>
      `;
    }).join("");

    timeline.innerHTML = timelineHtml;

  } catch (err) {
    if (timeline) {
      timeline.innerHTML = `
        <div style="text-align: center; padding: 25px; color: #ef4444; background: rgba(239,68,68,0.1); border-radius: 8px;">
          ❌ ${err.message}
        </div>
      `;
    }
  }
}

function fecharModalRastreioSro() {
  const modal = document.getElementById("modalRastreioSro");
  if (modal) modal.style.display = "none";
}



// ==========================================================================
// ETAPA C1 — DASHBOARD OPERACIONAL (LEITURATURSO DB EXCLUSIVA)
// ==========================================================================
let dashboardState = {
  periodo: "mes_atual",
  dataInicio: "",
  dataFim: ""
};

let chartTranspInstance = null;
let chartServInstance = null;

function initDashboard() {
  const dashPeriodoChips = document.querySelectorAll("#dashPeriodoChips .chip");
  const dashDataInicio = document.getElementById("dashDataInicio");
  const dashDataFim = document.getElementById("dashDataFim");

  if (dashPeriodoChips) {
    dashPeriodoChips.forEach(btn => {
      btn.addEventListener("click", () => {
        dashPeriodoChips.forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        dashboardState.periodo = btn.dataset.dashperiodo;
        carregarDashboardStats();
      });
    });
  }

  if (dashDataInicio) {
    dashDataInicio.addEventListener("change", () => {
      dashboardState.dataInicio = dashDataInicio.value;
      if (dashboardState.dataInicio && dashboardState.dataFim) {
        dashboardState.periodo = "personalizado";
        dashPeriodoChips.forEach(c => c.classList.remove("active"));
        carregarDashboardStats();
      }
    });
  }

  if (dashDataFim) {
    dashDataFim.addEventListener("change", () => {
      dashboardState.dataFim = dashDataFim.value;
      if (dashboardState.dataInicio && dashboardState.dataFim) {
        dashboardState.periodo = "personalizado";
        dashPeriodoChips.forEach(c => c.classList.remove("active"));
        carregarDashboardStats();
      }
    });
  }

  // Carregar dados na abertura (Zero chamadas Omie / SRO / Portal Postal)
  carregarDashboardStats();
}

async function carregarDashboardStats() {
  try {
    const params = new URLSearchParams({
      action: "dashboard_stats",
      periodo: dashboardState.periodo,
      data_inicio: dashboardState.dataInicio,
      data_fim: dashboardState.dataFim
    });

    const res = await fetch(`/.netlify/functions/turso-db?${params.toString()}`);
    const data = await safeFetchJson(res);

    if (!data || !data.expedicoes) return;

    // 1. CARDS EXPEDIÇÕES FATURADAS
    const exp = data.expedicoes;
    const elFaturadas = document.getElementById("dashCardFaturadas");
    const elPedidos = document.getElementById("dashCardPedidos");
    const elRemessas = document.getElementById("dashCardRemessas");
    const elOrigemNaoId = document.getElementById("dashCardOrigemNaoId");

    if (elFaturadas) elFaturadas.textContent = exp.total_faturadas || 0;
    if (elPedidos) elPedidos.textContent = exp.pedidos || 0;
    if (elRemessas) elRemessas.textContent = exp.remessas || 0;
    if (elOrigemNaoId) elOrigemNaoId.textContent = exp.origem_nao_identificada || 0;

    // 2. CARDS PROCESSO DE ETIQUETAS
    const etq = data.etiquetas || {};
    const elGeradas = document.getElementById("dashCardGeradas");
    const elAguardando = document.getElementById("dashCardAguardandoImp");
    const elImpressas = document.getElementById("dashCardImpressas");
    const elCanceladas = document.getElementById("dashCardCanceladas");

    if (elGeradas) elGeradas.textContent = etq.geradas || 0;
    if (elAguardando) elAguardando.textContent = etq.aguardando_impressao || 0;
    if (elImpressas) elImpressas.textContent = etq.impressas || 0;
    if (elCanceladas) elCanceladas.textContent = etq.canceladas || 0;

    // 2.5 CARDS DE RASTREAMENTO (SRO CACHE)
    const rst = data.rastreamento || {};
    const elPostadas = document.getElementById("dashCardPostadas");
    const elEmTransito = document.getElementById("dashCardEmTransito");
    const elSaiuEntrega = document.getElementById("dashCardSaiuEntrega");
    const elEntregues = document.getElementById("dashCardEntregues");
    const elOcorrencias = document.getElementById("dashCardOcorrencias");
    const elEtqExpiradas = document.getElementById("dashCardEtiquetasExpiradas");
    const elAgRetirada = document.getElementById("dashCardAguardandoRetirada");
    const elDevolucao = document.getElementById("dashCardDevolucao");

    if (elPostadas) elPostadas.textContent = rst.postado || 0;
    if (elEmTransito) elEmTransito.textContent = rst.em_transito || 0;
    if (elSaiuEntrega) elSaiuEntrega.textContent = rst.saiu_para_entrega || 0;
    if (elEntregues) elEntregues.textContent = rst.entregue || 0;
    if (elOcorrencias) elOcorrencias.textContent = rst.ocorrencia || 0;
    if (elEtqExpiradas) elEtqExpiradas.textContent = rst.etiqueta_expirada || 0;
    if (elAgRetirada) elAgRetirada.textContent = rst.aguardando_retirada || 0;
    if (elDevolucao) elDevolucao.textContent = rst.devolucao || 0;

    // 3. TOP INDICADORES OPERACIONAIS
    const ind = data.indicadores || {};
    const elTopTransp = document.getElementById("dashTopTransp");
    const elTopServico = document.getElementById("dashTopServico");
    const elClientes = document.getElementById("dashClientesDistintos");

    if (elTopTransp) elTopTransp.textContent = ind.top_transportadora || "--";
    if (elTopServico) elTopServico.textContent = ind.top_servico || "--";
    if (elClientes) elClientes.textContent = ind.total_clientes_distintos || 0;

    // 4. ÚLTIMA SINCRONIZAÇÃO OMIE
    const sync = data.ultima_sync_omie;
    const elSyncData = document.getElementById("dashUltimaSyncData");
    const elSyncMetricas = document.getElementById("dashUltimaSyncMetricas");

    if (sync) {
      const dtStr = sync.finalizado_em ? sync.finalizado_em.replace('T', ' ').substring(0, 16) : '--/--/----';
      if (elSyncData) elSyncData.textContent = dtStr;
      if (elSyncMetricas) {
        elSyncMetricas.textContent = `Encontradas: ${sync.encontradas || 0} | Novas: ${sync.novas || 0} | Erros: ${sync.erros || 0}`;
      }
    } else {
      if (elSyncData) elSyncData.textContent = "Nenhuma sync registrada";
      if (elSyncMetricas) elSyncMetricas.textContent = "";
    }

    // 5. RENDERIZAR GRÁFICOS
    renderChartsDashboard(data.transportadoras || [], data.servicos || []);

  } catch (err) {
    console.error("Erro ao carregar métricas do Dashboard Turso DB:", err);
  }
}

function renderChartsDashboard(transportadoras, servicos) {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js não carregado. Gráficos do Dashboard omitidos.");
    return;
  }

  const colorPalette = [
    "#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f87171",
    "#a78bfa", "#f472b6", "#60a5fa", "#4ade80", "#94a3b8"
  ];

  // 1. GRÁFICO TRANSPORTADORAS (DONUT)
  const ctxTransp = document.getElementById("chartTransportadoras");
  if (ctxTransp) {
    if (chartTranspInstance) chartTranspInstance.destroy();

    const labels = transportadoras.map(t => t.nome);
    const dataVals = transportadoras.map(t => t.qtd);

    chartTranspInstance = new Chart(ctxTransp, {
      type: "doughnut",
      data: {
        labels: labels.length > 0 ? labels : ["Sem Dados"],
        datasets: [{
          data: dataVals.length > 0 ? dataVals : [1],
          backgroundColor: colorPalette.slice(0, Math.max(1, labels.length)),
          borderWidth: 2,
          borderColor: "#0f172a"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: "#cbd5e1", font: { family: "Inter", size: 11 } }
          }
        }
      }
    });
  }

  // 2. GRÁFICO SERVIÇOS (BAR / DONUT)
  const ctxServ = document.getElementById("chartServicos");
  if (ctxServ) {
    if (chartServInstance) chartServInstance.destroy();

    const labels = servicos.map(s => s.nome);
    const dataVals = servicos.map(s => s.qtd);

    chartServInstance = new Chart(ctxServ, {
      type: "bar",
      data: {
        labels: labels.length > 0 ? labels : ["Sem Dados"],
        datasets: [{
          label: "Quantidade",
          data: dataVals.length > 0 ? dataVals : [0],
          backgroundColor: "#818cf8",
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 10 } },
            grid: { color: "#1e293b" }
          },
          y: {
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 10 }, precision: 0 },
            grid: { color: "#1e293b" }
          }
        }
      }
    });
  }
}

// NAVEGAÇÃO DOS CARDS PARA AS ABAS (INTEGRADO COM SIDEBAR DO DRP)
function navegarParaAba1(tipoOrigem = "TODOS") {
  if (typeof window.navegarParaAba === "function") {
    window.navegarParaAba("tab-correios-faturados");
    if (tipoOrigem !== "TODOS") {
      setTimeout(() => {
        const chip = document.querySelector(`#tipoOrigemChips .chip[data-origem="${tipoOrigem}"]`);
        if (chip) chip.click();
      }, 100);
    }
  }
}


async function carregarEtiquetasTotalExpress() {
  try {
    const res = await fetch("/.netlify/functions/total-express?action=listar");
    const data = await safeFetchJson(res);
    if (!res.ok || !data.sucesso) return;
    const body = document.getElementById("tableBodyAguardando");
    if (!body) return;
    const rows = (data.encomendas || []).filter(item => item.awb && item.status !== 'CANCELADO').map(item => `<tr data-total-express="1"><td><input type="checkbox" checked></td><td>${item.pedido || ""}<br><small>${item.awb}</small></td><td>${item.tipo_servico || ""}</td><td>${item.destinatario || "Total Express"}</td><td>${item.rota || ""}</td><td><div class="btn-action-group" style="display: flex; gap: 4px; flex-wrap: wrap;"><button class="btn btn-sm btn-primary" onclick="visualizarEtiquetaTotalExpress('${encodeURIComponent(item.awb)}')">Visualizar / Imprimir</button><button class="btn btn-sm btn-danger" style="padding: 3px 6px; font-size: 0.72rem;" onclick="cancelarEtiquetaTotalExpress('${encodeURIComponent(item.awb)}')">Cancelar</button></div></td></tr>`).join("");
    body.querySelectorAll("tr[data-total-express]").forEach(row => row.remove());
    if (rows) body.insertAdjacentHTML("afterbegin", rows);
  } catch (error) { console.error("Falha ao carregar etiquetas Total Express:", error); }
}

async function visualizarEtiquetaTotalExpress(awbEncoded) {
  const awb = decodeURIComponent(awbEncoded);
  const res = await fetch("/.netlify/functions/total-express?action=etiqueta", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({awb})});
  const data = await safeFetchJson(res);
  if (!res.ok || !data.pdfBase64) { alert(data.erro || "Etiqueta indisponível"); return; }
  const win = window.open("");
  if (!win) { alert("Permita pop-ups para visualizar ou imprimir a etiqueta."); return; }
  win.document.write(`<iframe style="border:0;width:100%;height:100%" src="data:application/pdf;base64,${data.pdfBase64}"></iframe>`);
  win.document.close();
}
window.visualizarEtiquetaTotalExpress = visualizarEtiquetaTotalExpress;

async function cancelarEtiquetaTotalExpress(awbEncoded) {
  const awb = decodeURIComponent(awbEncoded);
  if (!confirm("Deseja realmente cancelar a etiqueta Total Express AWB " + awb + "?")) return;
  try {
    const res = await fetch("/.netlify/functions/total-express?action=cancelar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ awb: awb })
    });
    const data = await safeFetchJson(res);
    if (res.ok && data.sucesso) {
      alert("Etiqueta Total Express cancelada com sucesso!");
      await carregarEtiquetasTotalExpress();
    } else {
      alert("Falha ao cancelar: " + (data.erro || data.mensagem || "Erro desconhecido"));
    }
  } catch (err) {
    alert("Erro de conexao ao cancelar: " + err.message);
  }
}
window.cancelarEtiquetaTotalExpress = cancelarEtiquetaTotalExpress;

async function atualizarRastreamentosSRO() {
  const btn = document.getElementById("btnAtualizarRastreios");
  const prog = document.getElementById("dashRastreioProgress");
  
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = "⏳ Atualizando...";
  }
  if (prog) {
    prog.style.display = "block";
    prog.innerHTML = "⏳ <strong>Consultando API SRO dos Correios...</strong><br>Atualizando cache do Turso DB em lote controlado. Aguarde um instante...";
  }

  try {
    const res = await fetch("/.netlify/functions/turso-db", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "atualizar_rastreamentos", limit: 50 })
    });
    const data = await safeFetchJson(res);
    const m = data?.metricas || {};

    if (prog) {
      prog.innerHTML = "✅ <strong>Rastreamentos Atualizados!</strong><br>" +
        "Objetos elegíveis: <strong>" + (m.elegiveis || 0) + "</strong> | " +
        "Consultados: <strong>" + (m.consultados || 0) + "</strong> | " +
        "Ignorados por cache recente (< 60 min): <strong>" + (m.ignorados_cache_recente || 0) + "</strong> | " +
        "Já finalizados (Entregues): <strong>" + (m.ignorados_finalizados || 0) + "</strong> | " +
        "Erros: <strong>" + (m.erros || 0) + "</strong>";
    }

    // Recarregar métricas do Dashboard
    await carregarDashboardStats();

  } catch (err) {
    console.error("Erro ao atualizar rastreamentos SRO:", err);
    if (prog) prog.innerHTML = "❌ <strong>Erro ao atualizar rastreamentos:</strong> " + err.message;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "🔄 Atualizar Rastreamentos";
    }
  }
}


// ==========================================================================
// EMISSÃO DE PRÉ-POSTAGENS (ABA 1 & MODAL DE EDIÇÃO)
// ==========================================================================

async function emitirPedidoObjeto(ped, qtdEtiquetas = 1) {
  if ((ped.transportadora_normalizada || "").toUpperCase() === "TOTAL EXPRESS") {
    const payload = {
      numero_pedido: String(ped.numero_pedido || ped.numero_remessa || ""), numero_remessa: String(ped.numero_remessa || ""),
      numero_nf: String(ped.numero_nf || ""), serie_nf: String(ped.serie_nf || "1"), chave_nfe: String(ped.chave_nfe || ""),
      data_emissao: ped.data_emissao || "", valor_nf: Number(ped.valor_nf || 0), peso_kg: Number(ped.peso_kg || 0),
      cfop_nf: ped.cfop_nf || "", volumes: Number(ped.qtd_etiquetas || 1), natureza: ped.natureza || "",
      cliente_nome: ped.destinatario?.nome || "", cliente_cpf_cnpj: ped.destinatario?.cpfCnpj || "",
      cep: ped.destinatario?.endereco?.cep || "", logradouro: ped.destinatario?.endereco?.logradouro || "",
      numero: ped.destinatario?.endereco?.numero || "", complemento: ped.destinatario?.endereco?.complemento || "",
      bairro: ped.destinatario?.endereco?.bairro || "", cidade: ped.destinatario?.endereco?.cidade || "", uf: ped.destinatario?.endereco?.uf || "",
      destinatario: {...(ped.destinatario || {}), endereco: ped.destinatario?.endereco || {}}
    };
    const response = await fetch("/.netlify/functions/total-express", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({pedido:payload})});
    const result = await safeFetchJson(response);
    if (!response.ok || result.erro) throw new Error((result.erros_validacao || [result.erro || "Falha Smart PUDO"]).join("; "));
    const records = result.retorno?.encomendas || [];
    if (records.length) {
      const awb = records[0].volumes?.[0]?.awb;
      const pdfResponse = await fetch("/.netlify/functions/total-express?action=etiqueta", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({awb: awb, pedido: payload})});
      const pdf = await safeFetchJson(pdfResponse);
      if (!pdfResponse.ok || !pdf.pdfBase64) throw new Error(pdf.erro || "Etiqueta Total Express indisponível");
      const win = window.open("");
      if (!win) throw new Error("Permita pop-ups para visualizar/imprimir a etiqueta.");
      win.document.write(`<iframe style="border:0;width:100%;height:100%" src="data:application/pdf;base64,${pdf.pdfBase64}"></iframe>`);
      win.document.close();
    }
    return records.map(item => ({codigoObjeto:item.volumes?.[0]?.awb, pedido:item.pedido, transportadora:"TOTAL EXPRESS"}));
  }
  const transpNorm = (ped.transportadora_normalizada || "").toUpperCase();
  const servico = (ped.forma_envio || ped.servico || "PAC").toUpperCase();
  const isRetiradaGuarita = transpNorm === "RETIRADA GUARITA" || servico === "RETIRADA_GUARITA";
  const isRetiradaEstoque = transpNorm === "RETIRADA ESTOQUE" || servico === "RETIRADA_ESTOQUE";
  if (isRetiradaGuarita || isRetiradaEstoque) {
    const pickupService = isRetiradaGuarita ? "RETIRADA_GUARITA" : "RETIRADA_ESTOQUE";
    const orderId = String(ped.numero_pedido || ped.numero_remessa || ped.numero_nf || "SEM_PEDIDO").trim();
    const safeId = orderId.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 48);
    const totalEmitir = Math.max(1, parseInt(qtdEtiquetas, 10) || 1);
    const resultados = [];
    for (let i = 0; i < totalEmitir; i++) {
      const volSuffix = totalEmitir > 1 ? `_V${i + 1}` : "";
      const obsVol = totalEmitir > 1 ? `${ped.obs_entrega || ped.obs_venda || ""} (Vol. ${i + 1}/${totalEmitir})`.trim() : (ped.obs_entrega || ped.obs_venda || "");
      const payload = {
        pedido: orderId,
        numero_nf: String(ped.numero_nf || ""), serie_nf: String(ped.serie_nf || "1"), chave_nfe: String(ped.chave_nfe || ""),
        id_prepostagem: `${pickupService}_${safeId}${volSuffix}`,
        codigo_objeto: "",
        servico: pickupService,
        destinatario: ped.destinatario?.nome || "CLIENTE",
        cpf_cnpj_destinatario: String(ped.destinatario?.cpfCnpj || "").replace(/\D/g, ""),
        email_destinatario: ped.email_destinatario || "", telefone_destinatario: ped.telefone_destinatario || "",
        logradouro: ped.destinatario?.endereco?.logradouro || "", numero: ped.destinatario?.endereco?.numero || "",
        complemento: ped.destinatario?.endereco?.complemento || "", bairro: ped.destinatario?.endereco?.bairro || "",
        cidade: ped.destinatario?.endereco?.cidade || "", uf: ped.destinatario?.endereco?.uf || "", cep: String(ped.destinatario?.endereco?.cep || "").replace(/\D/g, ""),
        obs_entrega: obsVol,
        valor_frete: 0, origem_postagem: pickupService, status: "PRONTO", status_rotulo: "PRONTO"
      };
      const response = await fetch("/.netlify/functions/turso-db?action=save_prepostagem", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await safeFetchJson(response);
      if (!response.ok || data.error) throw new Error(data.error || "Falha ao registrar retirada no Turso.");
      resultados.push({ idPrePostagem: data.id_prepostagem || payload.id_prepostagem, codigoObjeto: "", servico: pickupService });
    }
    return resultados;
  }
  const isSouza = transpNorm === "SOUZA" || servico.includes("SOUZA") || servico.includes("ENTREGA_PROPRIA") || servico.includes("ENTREGA LOCAL");
  const isModico = servico.includes("MODICO") || servico.includes("MÓDICO") || servico.includes("20133");
  const codigoServico = servico.includes("SEDEX") ? "03220" : (servico.includes("MINI") ? "04227" : (isModico ? "20133" : (isSouza ? "SOUZA" : "03298")));

  const dest = ped.destinatario || {};
  const end = dest.endereco || {};

  const payload = {
    pedido: String(ped.numero_pedido || ped.numero_remessa || "AVULSO"),
    numero_nf: String(ped.numero_nf || ""),
    chave_nfe: String(ped.chave_nfe || ""),
    servico: isModico ? "IMPRESSO_MODICO" : servico,
    codigoServico: codigoServico,
    pesoInformado: Math.max(300, Math.round(Number(ped.peso_kg || 0.3) * 1000)),
    destinatario: {
      nome: dest.nome || "CLIENTE",
      cpfCnpj: String(dest.cpfCnpj || "").replace(/\D/g, ""),
      endereco: {
        cep: String(end.cep || "").replace(/\D/g, ""),
        logradouro: end.logradouro || "Rua",
        numero: end.numero || "S/N",
        complemento: end.complemento || "",
        bairro: end.bairro || "Centro",
        cidade: end.cidade || "Fortaleza",
        uf: end.uf || "CE"
      }
    }
  };

  const resultados = [];
  const totalEmitir = Math.max(1, parseInt(qtdEtiquetas, 10) || 1);

  for (let i = 0; i < totalEmitir; i++) {
    if (isSouza) {
      // Entrega Própria Souza (Fortaleza/RMF): aloca range SZ sequencial exclusivo no Turso DB
      const resTurso = await fetch("/.netlify/functions/turso-db?action=save_prepostagem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pedido: payload.pedido,
          numero_nf: payload.numero_nf,
          chave_nfe: payload.chave_nfe,
          destinatario: payload.destinatario.nome,
          cpf_cnpj_destinatario: payload.destinatario.cpfCnpj,
          cep: payload.destinatario.endereco.cep,
          logradouro: payload.destinatario.endereco.logradouro,
          numero: payload.destinatario.endereco.numero,
          complemento: payload.destinatario.endereco.complemento,
          bairro: payload.destinatario.endereco.bairro,
          cidade: payload.destinatario.endereco.cidade,
          uf: payload.destinatario.endereco.uf,
          servico: "ENTREGA_PROPRIA",
          obs_entrega: totalEmitir > 1 ? `${ped.obs_entrega || ped.obs_venda || ""} (Vol. ${i + 1}/${totalEmitir})`.trim() : (ped.obs_entrega || ped.obs_venda || ""),
          valor_frete: Number(ped.valor_frete || 11.50) || 11.50,
          origem_postagem: "SOUZA_LOCAL",
          status: "PRONTO"
        })
      });
      const dataTurso = await safeFetchJson(resTurso);
      if (!resTurso.ok || dataTurso.error) {
        throw new Error(dataTurso.error || "Erro ao salvar Entrega Própria no Turso DB");
      }
      resultados.push({
        idPrePostagem: dataTurso.id_prepostagem || `SOUZA_${dataTurso.codigo_objeto}`,
        codigoObjeto: dataTurso.codigo_objeto,
        servico: "ENTREGA_PROPRIA"
      });
    } else if (isModico) {
      // Impresso Módico: salva diretamente no Turso DB (que aloca o range e calcula o DV SRO)
      const resTurso = await fetch("/.netlify/functions/turso-db?action=save_prepostagem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pedido: payload.pedido,
          numero_nf: payload.numero_nf,
          chave_nfe: payload.chave_nfe,
          destinatario: payload.destinatario.nome,
          cpf_cnpj_destinatario: payload.destinatario.cpfCnpj,
          cep: payload.destinatario.endereco.cep,
          logradouro: payload.destinatario.endereco.logradouro,
          numero: payload.destinatario.endereco.numero,
          complemento: payload.destinatario.endereco.complemento,
          bairro: payload.destinatario.endereco.bairro,
          cidade: payload.destinatario.endereco.cidade,
          uf: payload.destinatario.endereco.uf,
          servico: "IMPRESSO_MODICO",
          status: "MODICO_GERADO"
        })
      });
      const dataTurso = await safeFetchJson(resTurso);
      if (!resTurso.ok || dataTurso.error) {
        throw new Error(dataTurso.error || "Erro ao gerar Impresso Módico no Turso DB");
      }
      resultados.push({
        idPrePostagem: `MODICO_${dataTurso.codigo_objeto}`,
        codigoObjeto: dataTurso.codigo_objeto,
        servico: "IMPRESSO_MODICO"
      });
    } else {
      // PAC / SEDEX / MINI ENVIOS via CWS Correios
      const resCws = await fetch("/.netlify/functions/correios-prepostagem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const dataCws = await safeFetchJson(resCws);
      if (!resCws.ok || dataCws.error) {
        throw new Error(dataCws.detalhe ? JSON.stringify(dataCws.detalhe) : (dataCws.error || "Erro ao criar pré-postagem CWS"));
      }
      resultados.push({
        idPrePostagem: dataCws.id || dataCws.idPrePostagem,
        codigoObjeto: dataCws.codigoObjeto,
        servico: servico
      });
    }
  }

  return resultados;
}

async function emitirUnico(idx) {
  const ped = todosPedidos[idx];
  if (!ped) return;

  const inpRow = document.getElementById(`qtdEtqRow_${idx}`);
  const qtd = Math.max(1, parseInt(inpRow ? inpRow.value : (ped.qtd_etiquetas || 1), 10) || 1);
  ped.qtd_etiquetas = qtd;

  const descQtd = qtd > 1 ? `${qtd} etiquetas (volumes)` : `1 etiqueta`;
  if (!confirm(`Deseja emitir ${descQtd} de Pré-Postagem para ${ped.destinatario?.nome || 'este cliente'} (${ped.forma_envio || 'PAC'})?`)) {
    return;
  }

  try {
    const gerados = await emitirPedidoObjeto(ped, qtd);
    const cods = gerados.map(g => g.codigoObjeto).join(", ");
    alert(`✅ Pré-postagem (${descQtd}) gerada com sucesso!
Objeto(s): ${cods}

Disponível na Aba 2 (Etiquetas para Impressão).`);
    await carregarEtiquetasDoTurso();
    if (typeof carregarDashboardStats === "function") carregarDashboardStats();
  } catch (err) {
    alert(`❌ Falha ao emitir pré-postagem: ${err.message}`);
  }
}

async function emitirSelecionados() {
  const chks = Array.from(document.querySelectorAll(".chk-pedido:checked"));
  if (chks.length === 0) {
    alert("Selecione pelo menos um pedido na tabela.");
    return;
  }

  let totalEtiquetasPrevistas = 0;
  chks.forEach(chk => {
    const idx = parseInt(chk.dataset.idx, 10);
    const ped = todosPedidos[idx];
    if (!ped) return;
    const inpRow = document.getElementById(`qtdEtqRow_${idx}`);
    const qtd = Math.max(1, parseInt(inpRow ? inpRow.value : (ped.qtd_etiquetas || 1), 10) || 1);
    ped.qtd_etiquetas = qtd;
    totalEtiquetasPrevistas += qtd;
  });

  if (!confirm(`Deseja gerar ${totalEtiquetasPrevistas} etiqueta(s) para os ${chks.length} pedido(s) selecionado(s)?`)) {
    return;
  }

  const btn = document.getElementById("btnEmitirLote");
  const origText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Emitindo Pré-Postagens...";
  }

  let sucessos = 0;
  let etiquetasGeradasTotal = 0;
  const erros = [];

  try {
    for (const chk of chks) {
      const idx = parseInt(chk.dataset.idx, 10);
      const ped = todosPedidos[idx];
      if (!ped) continue;
      const inpRow = document.getElementById(`qtdEtqRow_${idx}`);
      const qtd = Math.max(1, parseInt(inpRow ? inpRow.value : (ped.qtd_etiquetas || 1), 10) || 1);
      ped.qtd_etiquetas = qtd;

      try {
        const gerados = await emitirPedidoObjeto(ped, qtd);
        sucessos++;
        etiquetasGeradasTotal += gerados.length;
        chk.checked = false;
      } catch (e) {
        erros.push(`#${ped.numero_pedido || ped.numero_nf}: ${e.message}`);
      }
    }

    await carregarEtiquetasDoTurso();
    if (typeof carregarDashboardStats === "function") carregarDashboardStats();

    let msg = `✅ Processo finalizado!
Pedidos processados: ${sucessos}
Total de Etiquetas geradas: ${etiquetasGeradasTotal}
Falhas: ${erros.length}`;
    if (erros.length > 0) {
      msg += `

Detalhes das falhas:
` + erros.join("\n");
    }
    alert(msg);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origText;
    }
    atualizarBotaoEmissao();
  }
}

function abrirModalEditarPedido(idx) {
  const ped = todosPedidos[idx];
  if (!ped) return;

  const modal = document.getElementById("modalEditPedido");
  if (!modal) return;

  const dest = ped.destinatario || {};
  const end = dest.endereco || {};

  document.getElementById("editPedidoIdx").value = idx;
  const titulo = document.getElementById("modalPedidoTitulo");
  if (titulo) titulo.textContent = `👁️ Detalhes do Pedido #${ped.numero_pedido || ped.numero_nf || 'S/N'}`;

  document.getElementById("editNome").value = dest.nome || "";
  document.getElementById("editCpfCnpj").value = dest.cpfCnpj || "";
  document.getElementById("editLogradouro").value = end.logradouro || "";
  document.getElementById("editNumero").value = end.numero || "";
  document.getElementById("editComplemento").value = end.complemento || "";
  document.getElementById("editBairro").value = end.bairro || "";
  document.getElementById("editCidade").value = end.cidade || "";
  document.getElementById("editUf").value = end.uf || "";
  document.getElementById("editCep").value = end.cep || "";
  const inpObs = document.getElementById("editObsEntrega");
  if (inpObs) inpObs.value = ped.obs_entrega || ped.obs_venda || "";

  const selEnvio = document.getElementById("editFormaEnvio");
  if (selEnvio) {
    const f = (ped.forma_envio || ped.servico || "PAC").toUpperCase();
    const t = (ped.transportadora_normalizada || "").toUpperCase();
    if (t === "RETIRADA GUARITA" || f.includes("RETIRADA_GUARITA")) {
      selEnvio.value = "Retirada na Guarita";
    } else if (t === "RETIRADA ESTOQUE" || f.includes("RETIRADA_ESTOQUE")) {
      selEnvio.value = "Retirada no Estoque";
    } else if (t === "SOUZA" || f.includes("SOUZA") || f.includes("ENTREGA LOCAL") || f.includes("ENTREGA_PROPRIA")) {
      selEnvio.value = "Entrega Local (Souza)";
    } else if (t === "TOTAL EXPRESS" || f.includes("TOTAL")) {
      selEnvio.value = "Total Express";
    } else if (t === "J&T EXPRESS" || f.includes("J&T") || f.includes("JT")) {
      selEnvio.value = "J&T Express";
    } else if (f.includes("SEDEX")) {
      selEnvio.value = "SEDEX";
    } else if (f.includes("MINI")) {
      selEnvio.value = "Mini Envios";
    } else if (f.includes("MODICO") || f.includes("MÓDICO")) {
      selEnvio.value = "Impresso Módico";
    } else {
      selEnvio.value = "PAC";
    }
  }

  const inpQtd = document.getElementById("editQtdEtiquetas");
  if (inpQtd) {
    inpQtd.value = ped.qtd_etiquetas || 1;
    inpQtd.disabled = false;
  }

  modal.style.display = "flex";
}

function fecharModalPedido() {
  const modal = document.getElementById("modalEditPedido");
  if (modal) modal.style.display = "none";
}

async function salvarEEmitirModal() {
  const idx = parseInt(document.getElementById("editPedidoIdx").value, 10);
  const ped = todosPedidos[idx];
  if (!ped) return;

  ped.destinatario = ped.destinatario || {};
  ped.destinatario.endereco = ped.destinatario.endereco || {};

  ped.destinatario.nome = document.getElementById("editNome").value.trim();
  ped.destinatario.cpfCnpj = document.getElementById("editCpfCnpj").value.trim();
  ped.destinatario.endereco.logradouro = document.getElementById("editLogradouro").value.trim();
  ped.destinatario.endereco.numero = document.getElementById("editNumero").value.trim();
  ped.destinatario.endereco.complemento = document.getElementById("editComplemento").value.trim();
  ped.destinatario.endereco.bairro = document.getElementById("editBairro").value.trim();
  ped.destinatario.endereco.cidade = document.getElementById("editCidade").value.trim();
  ped.destinatario.endereco.uf = document.getElementById("editUf").value.trim().toUpperCase();
  ped.destinatario.endereco.cep = document.getElementById("editCep").value.trim();
  const inpObsSave = document.getElementById("editObsEntrega");
  if (inpObsSave) ped.obs_entrega = inpObsSave.value.trim();

  const formaSel = document.getElementById("editFormaEnvio").value;
  ped.forma_envio = formaSel;
  ped.servico = formaSel;
  if (formaSel === "Retirada na Guarita") {
    ped.transportadora_normalizada = "RETIRADA GUARITA";
    ped.servico = "RETIRADA_GUARITA";
  } else if (formaSel === "Retirada no Estoque") {
    ped.transportadora_normalizada = "RETIRADA ESTOQUE";
    ped.servico = "RETIRADA_ESTOQUE";
  } else if (formaSel === "Entrega Local (Souza)") {
    ped.transportadora_normalizada = "SOUZA";
    ped.servico = "ENTREGA_PROPRIA";
  } else if (formaSel === "Total Express") {
    ped.transportadora_normalizada = "TOTAL EXPRESS";
  } else if (formaSel === "J&T Express") {
    ped.transportadora_normalizada = "J&T EXPRESS";
  } else {
    ped.transportadora_normalizada = "CORREIOS";
  }

  const qtd = Math.max(1, parseInt(document.getElementById("editQtdEtiquetas").value || "1", 10) || 1);
  ped.qtd_etiquetas = qtd;
  const inpRow = document.getElementById(`qtdEtqRow_${idx}`);
  if (inpRow) inpRow.value = qtd;

  try {
    const res = await emitirPedidoObjeto(ped, qtd);
    fecharModalPedido();
    const cods = res.map(r => r.codigoObjeto).join(", ");
    const isPickup = (ped.transportadora_normalizada || "").startsWith("RETIRADA ");
    alert(isPickup
      ? `✅ Etiqueta de ${ped.transportadora_normalizada === "RETIRADA GUARITA" ? "retirada na guarita" : "retirada no estoque"} registrada.\nDisponível na Aba 2 (Etiquetas para Impressão).${ped.transportadora_normalizada === "RETIRADA GUARITA" ? " Também pode entrar na lista de conferência da Aba 5." : ""}`
      : `✅ Pré-postagem emitida com sucesso!\nObjeto(s): ${cods}`);
    await carregarEtiquetasDoTurso();
    if (typeof carregarDashboardStats === "function") carregarDashboardStats();
  } catch (err) {
    alert(`❌ Erro ao emitir pré-postagem: ${err.message}`);
  }
}

// ==========================================================================
// CANCELAMENTO DE PRÉ-POSTAGENS (ABA 2)
// ==========================================================================

async function executarCancelamentoItem(item, forcarLocal = false) {
  if (!item) return { sucesso: false, erro: "Item inválido" };
  try {
    const serv = (item.servico || "").toUpperCase();
    const idPre = item.idPrePostagem || "";
    const obj = item.objeto || "";
    const isModico = serv.includes("MODICO") || serv.includes("MÓDICO") || idPre.startsWith("MODICO_");
    const isSouza = serv.includes("SOUZA") || serv.includes("ENTREGA_PROPRIA") || serv.includes("ENTREGA LOCAL") || idPre.startsWith("SOUZA_") || obj.startsWith("SZ");

    const params = new URLSearchParams({
      id: idPre,
      codigoObjeto: obj,
      servico: isSouza ? "ENTREGA_PROPRIA" : (isModico ? "IMPRESSO_MODICO" : serv)
    });
    if (forcarLocal) {
      params.append("forcarLocal", "true");
    }

    const res = await fetch(`/.netlify/functions/correios-cancelar?${params.toString()}`, {
      method: "DELETE"
    });
    const data = await safeFetchJson(res);
    if (res.ok && (data.sucesso || data.ok)) {
      return { sucesso: true };
    }
    return { sucesso: false, erro: data.error || data.mensagem || "Erro ao cancelar", detalhes: data };
  } catch (err) {
    return { sucesso: false, erro: err.message };
  }
}

async function cancelarPrePostagem(idx) {
  const item = etiquetasGeradas[idx];
  if (!item) return;

  if (!confirm(`Deseja realmente cancelar a pré-postagem do objeto ${item.objeto || item.nf}?`)) {
    return;
  }

  const res = await executarCancelamentoItem(item);
  if (res.sucesso) {
    etiquetasGeradas.splice(idx, 1);
    renderEtiquetasGeradas();
    if (typeof carregarArquivoTurso === "function") carregarArquivoTurso();
    if (typeof carregarDashboardStats === "function") carregarDashboardStats();
    alert("✅ Pré-postagem cancelada com sucesso!");
  } else {
    if (confirm(`A API dos Correios rejeitou o cancelamento (${res.erro}).\n\nIsso ocorre quando a pré-postagem é antiga, teste ou já expirou no sistema dos Correios.\n\nDeseja FORÇAR o cancelamento no sistema para remover este item e liberar o pedido?`)) {
      const resForce = await executarCancelamentoItem(item, true);
      if (resForce.sucesso) {
        etiquetasGeradas.splice(idx, 1);
        renderEtiquetasGeradas();
        if (typeof carregarArquivoTurso === "function") carregarArquivoTurso();
        if (typeof carregarDashboardStats === "function") carregarDashboardStats();
        alert("✅ Pré-postagem cancelada e removida localmente com sucesso!");
        return;
      }
      alert(`❌ Falha ao forçar cancelamento local: ${resForce.erro}`);
      return;
    }
    alert(`❌ Falha ao cancelar: ${res.erro}`);
  }
}

async function cancelarPrePostagemArquivo(idx) {
  const item = etiquetasArquivoFiltrados[idx];
  if (!item) return;

  if (!confirm(`Deseja realmente cancelar a pré-postagem do objeto impresso ${item.objeto || item.nf}? O código será estornado.`)) {
    return;
  }

  const res = await executarCancelamentoItem(item);
  if (res.sucesso) {
    etiquetasArquivoFiltrados.splice(idx, 1);
    renderEtiquetasArquivo(etiquetasArquivoFiltrados);
    if (typeof carregarEtiquetasDoTurso === "function") carregarEtiquetasDoTurso();
    if (typeof carregarDashboardStats === "function") carregarDashboardStats();
    alert("✅ Etiqueta impressa cancelada e estornada com sucesso!");
  } else {
    if (confirm(`A API dos Correios rejeitou o cancelamento (${res.erro}).\n\nIsso ocorre quando a pré-postagem é antiga, teste ou já expirou no sistema dos Correios.\n\nDeseja FORÇAR o cancelamento no sistema para remover este item do histórico?`)) {
      const resForce = await executarCancelamentoItem(item, true);
      if (resForce.sucesso) {
        etiquetasArquivoFiltrados.splice(idx, 1);
        renderEtiquetasArquivo(etiquetasArquivoFiltrados);
        if (typeof carregarEtiquetasDoTurso === "function") carregarEtiquetasDoTurso();
        if (typeof carregarDashboardStats === "function") carregarDashboardStats();
        alert("✅ Etiqueta cancelada e removida localmente com sucesso!");
        return;
      }
      alert(`❌ Falha ao forçar cancelamento local: ${resForce.erro}`);
      return;
    }
    alert(`❌ Falha ao cancelar etiqueta impressa: ${res.erro}`);
  }
}

// ==========================================================================
// ABA 5: LISTA DE POSTAGEM (PLP)
// ==========================================================================

let objetosPlpElegiveis = [];
let listasPlpFechadas = [];

function initPlpTab() {
  const btnFiltrarObj = document.getElementById("btnFiltrarObjPlp");
  if (btnFiltrarObj) {
    btnFiltrarObj.addEventListener("click", carregarObjetosElegiveisPlp);
  }

  const chkAllObj = document.getElementById("chkSelectAllObjPlp");
  if (chkAllObj) {
    chkAllObj.addEventListener("change", (e) => {
      document.querySelectorAll(".chk-obj-plp").forEach(chk => {
        chk.checked = e.target.checked;
      });
      atualizarBotaoGerarPlp();
    });
  }

  const btnGerarLista = document.getElementById("btnGerarListaPlp");
  if (btnGerarLista) {
    btnGerarLista.addEventListener("click", gerarListaPostagemPlp);
  }

  const btnFiltrarPLP = document.getElementById("btnFiltrarPLP");
  if (btnFiltrarPLP) {
    btnFiltrarPLP.addEventListener("click", carregarListasPlpFechadas);
  }
}

function atualizarBotaoGerarPlp() {
  const btn = document.getElementById("btnGerarListaPlp");
  if (!btn) return;
  const sel = document.querySelectorAll(".chk-obj-plp:checked").length;
  btn.disabled = sel === 0;
  const transpSel = document.getElementById("plpTranspTab")?.value || "CORREIOS";
  if (transpSel === "TOTAL") {
    btn.textContent = sel > 0 ? `⚡ Fechar Manifesto Total Express (${sel} itens)` : `⚡ Fechar Manifesto Total Express`;
  } else if (transpSel === "SOUZA") {
    btn.textContent = sel > 0 ? `🚚 Fechar Romaneio Souza (${sel} itens)` : `🚚 Fechar Romaneio Souza`;
  } else if (transpSel === "GUARITA") {
    btn.textContent = sel > 0 ? `🏁 Fechar Lista Guarita (${sel} itens)` : `🏁 Fechar Lista Guarita`;
  } else {
    btn.textContent = sel > 0 ? `📜 Gerar Lista de Postagem (${sel} objetos)` : `📜 Gerar Lista de Postagem (PLP)`;
  }
}

async function carregarObjetosElegiveisPlp() {
  const tbody = document.getElementById("tableBodyObjPlp");
  const countEl = document.getElementById("totalCountObjPlp");
  const freteHeader = document.getElementById("plpTotalFreteHeader");
  if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="empty-state">⏳ Carregando objetos impressos elegíveis...</td></tr>`;

  try {
    const transpSel = document.getElementById("plpTranspTab")?.value || "TODOS";
    const btnCotar = document.getElementById("btnCotarFrenetLote");
    if (btnCotar) btnCotar.style.display = transpSel === "GUARITA" ? "none" : "";
    const params = new URLSearchParams({
      action: "list_disponiveis",
      data_inicio: document.getElementById("plpObjDataInicio")?.value || "",
      data_fim: document.getElementById("plpObjDataFim")?.value || "",
      servico: document.getElementById("plpObjServico")?.value || "TODOS",
      transportadora: transpSel !== "TODOS" ? transpSel : "",
      busca: document.getElementById("plpObjBusca")?.value || ""
    });

    const res = await fetch(`/.netlify/functions/lista-postagem?${params.toString()}`);
    const data = await safeFetchJson(res);
    objetosPlpElegiveis = data.disponiveis || data.objetos || [];

    if (countEl) countEl.textContent = objetosPlpElegiveis.length;
    const badgePend = document.getElementById("badgeCountPendentesSubaba");
    if (badgePend) badgePend.textContent = objetosPlpElegiveis.length;

    if (objetosPlpElegiveis.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Nenhum objeto impresso pendente de lista encontrado.</td></tr>`;
      if (freteHeader) freteHeader.textContent = "Total Fretes: R$ 0,00";
      atualizarBotaoGerarPlp();
      return;
    }

    if (tbody) {
      tbody.innerHTML = objetosPlpElegiveis.map((obj, i) => {
        const vf = Number(obj.valor_frete || 0);
        const freteColor = vf > 0 ? "#10b981" : "#f59e0b";
        const isGuarita = obj.servico === "RETIRADA_GUARITA";
        const tipoBadge = obj.tipo_item === "AVULSO" 
          ? `<span class="badge" style="background: rgba(236,72,153,0.2); color: #f472b6; border: 1px solid #db2777;">AVULSO</span>` 
          : `<span class="badge badge-primary">${obj.servico || '-'}</span>`;

        return `
        <tr>
          <td><input type="checkbox" class="chk-obj-plp" value="${obj.id}" data-idx="${i}" checked onchange="atualizarBotaoGerarPlp()"></td>
          <td>
            <strong>${isGuarita ? 'LOCAL - SEM RASTREIO' : (obj.codigo_objeto || '-')}</strong>
            ${obj.tipo_item === "AVULSO" && obj.descricao_avulsa ? `<div style="font-size: 0.72rem; color: #94a3b8;">${obj.descricao_avulsa}</div>` : ''}
          </td>
          <td>${tipoBadge}</td>
          <td>${obj.pedido || '-'}${obj.numero_nf ? ' / NF ' + obj.numero_nf : ''}</td>
          <td>${obj.destinatario || '-'}</td>
          <td>${obj.cidade || ''}/${obj.uf || ''}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 4px;">
              <span style="font-size: 0.75rem; color: #94a3b8;">R$</span>
              <input type="number" step="0.50" min="0" value="${vf.toFixed(2)}" 
                onchange="atualizarFretePrepostagemItem(${obj.id}, this.value, ${i})"
                style="width: 70px; background: #0f172a; border: 1px solid ${freteColor}; color: ${freteColor}; font-weight: 700; border-radius: 4px; padding: 2px 5px; text-align: right;">
              ${vf === 0 ? `<button type="button" class="btn btn-sm" onclick="cotarFrenetLinha(${obj.id}, '${obj.cep || ''}', ${i})" style="padding: 1px 4px; font-size: 0.68rem; background: #0284c7; color: #fff;" title="Cotar Frete Frenet">⚡</button>` : ''}
            </div>
          </td>
          <td><span class="badge ${obj.status_entrega === 'FINALIZADO' ? 'badge-success' : 'badge-secondary'}" style="font-size: 0.72rem;">${isGuarita ? 'AGUARDANDO RETIRADA' : (obj.status_entrega || 'EM_COLETA')}</span></td>
          <td style="font-size: 0.75rem; color: #94a3b8;">${obj.created_at ? obj.created_at.substring(0, 16).replace('T', ' ') : '-'}</td>
        </tr>
      `;
      }).join("");
    }
    const chkAll = document.getElementById("chkSelectAllObjPlp");
    if (chkAll) chkAll.checked = true;
    atualizarBotaoGerarPlp();
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="empty-state" style="color:#ef4444;">Erro: ${err.message}</td></tr>`;
  }
}

function atualizarBotaoGerarPlp() {
  const btn = document.getElementById("btnGerarListaPlp");
  const freteHeader = document.getElementById("plpTotalFreteHeader");
  const transpSel = document.getElementById("plpTranspTab")?.value || "CORREIOS";
  const chks = Array.from(document.querySelectorAll(".chk-obj-plp:checked"));
  const count = chks.length;

  let totalFrete = 0.0;
  chks.forEach(chk => {
    const idx = parseInt(chk.dataset.idx, 10);
    const item = objetosPlpElegiveis[idx];
    if (item) totalFrete += Number(item.valor_frete || 0);
  });

  if (freteHeader) {
    freteHeader.textContent = `Total Fretes: R$ ${totalFrete.toFixed(2)} (${count} selecionados)`;
  }

  if (!btn) return;
  btn.disabled = count === 0;

  const nomeDoc = transpSel === "GUARITA" ? "Lista de Retiradas da Guarita" : (transpSel === "SOUZA" ? "Romaneio Souza" : (transpSel === "TOTAL" ? "Manifesto Total" : (transpSel === "JT" ? "Romaneio J&T" : "Lista de Postagem (PLP)")));
  btn.textContent = count > 0 
    ? `📜 Fechar ${nomeDoc} (${count} itens | R$ ${totalFrete.toFixed(2)})` 
    : `📜 Fechar ${nomeDoc}`;
}

async function atualizarFretePrepostagemItem(idPrepostagem, novoValor, idx) {
  const val = parseFloat(novoValor) || 0.0;
  try {
    const res = await fetch("/.netlify/functions/turso-db?action=update_frete_prepostagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: idPrepostagem, valor_frete: val })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao salvar frete.");
    if (objetosPlpElegiveis[idx]) {
      objetosPlpElegiveis[idx].valor_frete = val;
    }
    atualizarBotaoGerarPlp();
  } catch (err) {
    alert("Falha ao salvar valor do frete: " + err.message);
  }
}

async function cotarFrenetLinha(idPrepostagem, cep, idx) {
  if (!cep) { alert("Este item não possui CEP para cotação."); return; }
  const cepLimpo = cep.replace(/\D/g, "");
  try {
    const res = await fetch(`/api/frenet/cotar?cep=${cepLimpo}&peso=0.5&valor=100`);
    const data = await safeFetchJson(res);
    const cotacoes = data.cotacoes || [];
    if (!cotacoes.length) throw new Error(data.error || "Nenhum frete retornado pela Frenet");

    // Procura Entrega Economica / Souza (padrao R$ 11.50) ou primeira cotacao
    let sel = cotacoes.find(c => {
      const s = (c.servico || "").toUpperCase();
      const t = (c.transportadora || "").toUpperCase();
      return s.includes("ECON") || s.includes("SOUZA") || t.includes("SOUZA") || t.includes("PERSONALIZADA");
    });
    if (!sel) sel = cotacoes[0];

    const valFrete = parseFloat(sel.valor !== undefined ? sel.valor : (sel.preco || 11.50)) || 11.50;
    await atualizarFretePrepostagemItem(idPrepostagem, valFrete, idx);
    await carregarObjetosElegiveisPlp();
  } catch (e) {
    alert(`Erro ao cotar via Frenet: ${e.message}`);
  }
}

async function cotarFretesPendentesFrenet() {
  const pendentes = objetosPlpElegiveis.filter(obj => !obj.valor_frete || Number(obj.valor_frete) === 0);
  if (pendentes.length === 0) {
    alert("Todos os objetos da lista já possuem frete calculado.");
    return;
  }

  const btn = document.getElementById("btnCotarFrenetLote");
  const origText = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = `⏳ Cotando ${pendentes.length} fretes...`; }

  let ok = 0;
  for (const item of pendentes) {
    const cep = (item.cep || "").replace(/\D/g, "");
    if (!cep) continue;
    try {
      const res = await fetch(`/api/frenet/cotar?cep=${cep}&peso=0.5&valor=100`);
      const data = await safeFetchJson(res);
      const cotacoes = data.cotacoes || [];
      if (cotacoes.length > 0) {
        let sel = cotacoes.find(c => {
          const s = (c.servico || "").toUpperCase();
          const t = (c.transportadora || "").toUpperCase();
          return s.includes("ECON") || s.includes("SOUZA") || t.includes("SOUZA") || t.includes("PERSONALIZADA");
        });
        if (!sel) sel = cotacoes[0];
        const valFrete = parseFloat(sel.valor !== undefined ? sel.valor : (sel.preco || 11.50)) || 11.50;
        await fetch("/.netlify/functions/turso-db?action=update_frete_prepostagem", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: item.id, valor_frete: valFrete })
        });
        ok++;
      }
    } catch (e) {
      console.warn("Erro ao cotar frete item", item.id, e);
    }
  }

  if (btn) { btn.disabled = false; btn.textContent = origText; }
  alert(`⚡ ${ok} frete(s) cotado(s) e atualizado(s) com sucesso via Frenet!`);
  await carregarObjetosElegiveisPlp();
}

function abrirModalNovaEntregaAvulsa() {
  const modal = document.getElementById("modalEntregaAvulsa");
  if (modal) {
    document.getElementById("avulsaDescricao").value = "";
    document.getElementById("avulsaDestinatario").value = "";
    document.getElementById("avulsaEndereco").value = "";
    document.getElementById("avulsaBairro").value = "";
    document.getElementById("avulsaCidade").value = "Fortaleza / CE";
    document.getElementById("avulsaCep").value = "";
    document.getElementById("avulsaValorFrete").value = "11.50";
    document.getElementById("avulsaObs").value = "";
    modal.style.display = "flex";
  }
}

function fecharModalNovaEntregaAvulsa() {
  const modal = document.getElementById("modalEntregaAvulsa");
  if (modal) modal.style.display = "none";
}

async function salvarNovaEntregaAvulsa() {
  const desc = document.getElementById("avulsaDescricao")?.value.trim();
  const dest = document.getElementById("avulsaDestinatario")?.value.trim();
  const end = document.getElementById("avulsaEndereco")?.value.trim();
  const bairro = document.getElementById("avulsaBairro")?.value.trim();
  const cidade = document.getElementById("avulsaCidade")?.value.trim() || "Fortaleza";
  const cep = document.getElementById("avulsaCep")?.value.trim();
  const frete = parseFloat(document.getElementById("avulsaValorFrete")?.value) || 11.50;
  const obs = document.getElementById("avulsaObs")?.value.trim();

  if (!desc || !dest) {
    alert("Preencha a descrição do serviço e o destinatário.");
    return;
  }

  try {
    const res = await fetch("/.netlify/functions/turso-db?action=save_prepostagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pedido: "AVULSO",
        numero_nf: "SEM_NF",
        destinatario: dest,
        logradouro: end || "Coleta / Entrega Externa",
        numero: "S/N",
        bairro: bairro || "Fortaleza",
        cidade: cidade,
        uf: "CE",
        cep: cep || "60000000",
        servico: "ENTREGA_PROPRIA",
        obs_entrega: obs,
        valor_frete: frete,
        tipo_item: "AVULSO",
        descricao_avulsa: desc,
        status: "PRONTO",
        status_impressao: "PRONTO",
        status_entrega: "EM_COLETA"
      })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao salvar entrega avulsa");

    fecharModalNovaEntregaAvulsa();
    alert(`✅ Entrega Avulsa registrada com código ${data.codigo_objeto}!\nJá disponível na Aba 2 (Etiquetas para Impressão) para imprimir o rótulo e na Aba 5 (Romaneio).`);
    await carregarEtiquetasDoTurso();
    await carregarObjetosElegiveisPlp();
  } catch (err) {
    alert(`Erro ao cadastrar entrega avulsa: ${err.message}`);
  }
}

async function gerarListaPostagemPlp() {
  const chks = Array.from(document.querySelectorAll(".chk-obj-plp:checked"));
  if (chks.length === 0) return;

  const ids = chks.map(c => parseInt(c.value, 10));
  const transpSel = document.getElementById("plpTranspTab")?.value || "CORREIOS";
  const tipoRomaneio = transpSel === "GUARITA" ? "RETIRADA_GUARITA" : (transpSel === "SOUZA" ? "SOUZA" : (transpSel === "TOTAL" ? "TOTAL_EXPRESS" : (transpSel === "JT" ? "JT_EXPRESS" : "CORREIOS")));

  let totalFrete = 0.0;
  chks.forEach(chk => {
    const idx = parseInt(chk.dataset.idx, 10);
    const item = objetosPlpElegiveis[idx];
    if (item) totalFrete += Number(item.valor_frete || 0);
  });

  const msgConfirm = transpSel === "GUARITA"
    ? `Confirmar a lista de conferência da GUARITA com ${ids.length} pedido(s)?`
    : transpSel === "SOUZA"
    ? `Confirmar fechamento do ROMANEIO ROBERTO SOUZA com ${ids.length} entrega(s)?\nTotal a pagar ao motorista: R$ ${totalFrete.toFixed(2)}`
    : `Confirmar o fechamento da Lista de Postagem (${transpSel}) com ${ids.length} objeto(s)?`;

  if (!confirm(msgConfirm)) return;

  try {
    const res = await fetch("/.netlify/functions/lista-postagem?action=create_lista", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        prepostagem_ids: ids,
        tipo_romaneio: tipoRomaneio,
        usuario: "OPERADOR"
      })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) {
      throw new Error(data.error || "Erro ao criar romaneio/PLP");
    }
    alert(`✅ Romaneio / Lista #${data.numero_lista} gerado com sucesso!`);
    await carregarObjetosElegiveisPlp();
    await carregarListasPlpFechadas();
  } catch (err) {
    alert(`❌ Erro ao fechar lista: ${err.message}`);
  }
}

async function carregarListasPlpFechadas() {
  const tbody = document.getElementById("tableBodyPLP");
  const badgeFechadas = document.getElementById("badgeCountFechadasSubaba");
  if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="empty-state">⏳ Carregando listas fechadas...</td></tr>`;

  try {
    const transpFiltro = document.getElementById("filtroTranspFechadas")?.value || "TODOS";
    const params = new URLSearchParams({
      action: "list_listas",
      data_inicio: document.getElementById("plpDataInicio")?.value || "",
      data_fim: document.getElementById("plpDataFim")?.value || "",
      transportadora: transpFiltro !== "TODOS" ? transpFiltro : "",
      numero_lista: document.getElementById("plpNumBusca")?.value || ""
    });

    const res = await fetch(`/.netlify/functions/lista-postagem?${params.toString()}`);
    const data = await safeFetchJson(res);
    listasPlpFechadas = data.listas || [];
    if (badgeFechadas) badgeFechadas.textContent = listasPlpFechadas.length;

    if (listasPlpFechadas.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Nenhuma lista ou romaneio gerado no período.</td></tr>`;
      return;
    }

    if (tbody) {
      tbody.innerHTML = listasPlpFechadas.map(l => {
        const isSouza = (l.tipo_romaneio || "").toUpperCase() === "SOUZA";
        const isGuarita = (l.tipo_romaneio || "").toUpperCase() === "RETIRADA_GUARITA";
        const isTotal = (l.tipo_romaneio || "").toUpperCase().includes("TOTAL");
        const badgeTipo = isGuarita
          ? `<span class="badge" style="background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid #059669;">🏁 GUARITA</span>`
          : isSouza
          ? `<span class="badge" style="background: rgba(14,165,233,0.2); color: #38bdf8; border: 1px solid #0284c7;">🚚 SOUZA</span>`
          : isTotal
          ? `<span class="badge" style="background: rgba(245,158,11,0.2); color: #f59e0b; border: 1px solid #d97706;">⚡ TOTAL EXPRESS</span>`
          : `<span class="badge badge-primary">📦 ${l.tipo_romaneio || 'CORREIOS'}</span>`;

        const freteDisplay = l.valor_total_frete ? `R$ ${Number(l.valor_total_frete).toFixed(2)}` : '-';

        return `
        <tr>
          <td><strong>#${l.numero_lista}</strong></td>
          <td>${badgeTipo}</td>
          <td>${l.data_geracao ? l.data_geracao.substring(0, 16).replace('T', ' ') : '-'}</td>
          <td><strong>${l.quantidade_objetos || 0}</strong></td>
          <td style="color: #10b981; font-weight: 700;">${freteDisplay}</td>
          <td><span class="badge ${l.status === 'CANCELADA' ? 'badge-danger' : 'badge-success'}">${l.status || 'GERADA'}</span></td>
          <td>
            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
              <button class="btn btn-sm btn-primary" onclick="visualizarModalListaPlp(${l.id})">👁️ Detalhes / PDF</button>
              ${isSouza ? `<button class="btn btn-sm" onclick="abrirModalMobileMotorista(${l.id})" style="background: #059669; color: #fff; font-weight: 700;" title="Abrir painel mobile de entrega e assinaturas">📱 App Motorista</button>` : ''}
              ${l.status !== 'CANCELADA' 
                ? `<button class="btn btn-sm btn-danger" onclick="cancelarListaPlpFechada(${l.id}, '${l.numero_lista}')">❌ Cancelar</button>` 
                : `<button class="btn btn-sm" onclick="excluirListaPlpCancelada(${l.id}, '${l.numero_lista}')" style="background:#475569; color:#f8fafc;" title="Excluir lista cancelada do histórico">🗑️ Excluir</button>`}
            </div>
          </td>
        </tr>
      `;
      }).join("");
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="empty-state" style="color:#ef4444;">Erro: ${err.message}</td></tr>`;
  }
}

function alternarSubabaPlp(tipo) {
  const pend = document.getElementById("subabaContainerPlpPendentes");
  const fech = document.getElementById("subabaContainerPlpFechadas");
  const btnP = document.getElementById("subtabBtnPlpPendentes");
  const btnF = document.getElementById("subtabBtnPlpFechadas");

  if (tipo === "FECHADAS") {
    if (pend) pend.style.display = "none";
    if (fech) fech.style.display = "block";
    if (btnP) {
      btnP.style.background = "rgba(14, 165, 233, 0.15)";
      btnP.style.color = "#38bdf8";
      btnP.style.border = "1px solid #0ea5e9";
    }
    if (btnF) {
      btnF.style.background = "#0284c7";
      btnF.style.color = "#fff";
      btnF.style.border = "none";
    }
    carregarListasPlpFechadas();
  } else {
    if (pend) pend.style.display = "block";
    if (fech) fech.style.display = "none";
    if (btnF) {
      btnF.style.background = "rgba(14, 165, 233, 0.15)";
      btnF.style.color = "#38bdf8";
      btnF.style.border = "1px solid #0ea5e9";
    }
    if (btnP) {
      btnP.style.background = "#0284c7";
      btnP.style.color = "#fff";
      btnP.style.border = "none";
    }
    carregarObjetosElegiveisPlp();
  }
}
window.alternarSubabaPlp = alternarSubabaPlp;

async function cancelarListaPlpFechada(listaId, numLista) {
  if (!confirm(`Deseja realmente cancelar a Lista / Romaneio #${numLista}? Os objetos retornarão como pendentes de lista.`)) {
    return;
  }
  try {
    const res = await fetch("/.netlify/functions/lista-postagem?action=cancel_lista", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lista_id: listaId, numero_lista: numLista, usuario: "OPERADOR" })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao cancelar lista");
    alert(`✅ Lista #${numLista} cancelada com sucesso! Os objetos retornaram para a fila de pendentes.`);
    await carregarListasPlpFechadas();
    await carregarObjetosElegiveisPlp();
    if (typeof carregarEntregasAba10Motorista === "function") {
      await carregarEntregasAba10Motorista();
    }
  } catch (err) {
    alert(`Erro ao cancelar lista: ${err.message}`);
  }
}
window.cancelarListaPlpFechada = cancelarListaPlpFechada;

async function excluirListaPlpCancelada(listaId, numLista) {
  if (!confirm(`Deseja excluir permanentemente o registro da Lista / Romaneio #${numLista} do histórico?`)) {
    return;
  }
  try {
    const res = await fetch("/.netlify/functions/lista-postagem?action=delete_lista", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lista_id: listaId, numero_lista: numLista })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao excluir lista");
    alert(`🗑️ Registro da Lista #${numLista} removido do histórico.`);
    await carregarListasPlpFechadas();
    await carregarObjetosElegiveisPlp();
  } catch (err) {
    alert(`Erro ao excluir registro: ${err.message}`);
  }
}
window.excluirListaPlpCancelada = excluirListaPlpCancelada;

function fecharModalLista() {
  const modal = document.getElementById("modalVisualizarLista");
  if (modal) modal.style.display = "none";
}
window.fecharModalLista = fecharModalLista;

async function visualizarModalListaPlp(id) {
  const modal = document.getElementById("modalVisualizarLista");
  if (!modal) return;

  try {
    const res = await fetch(`/.netlify/functions/lista-postagem?action=get_lista&lista_id=${id}`);
    const data = await safeFetchJson(res);
    if (!data.lista) throw new Error("Lista não encontrada");

    const l = data.lista;
    const itens = data.itens || [];
    const isSouza = (l.tipo_romaneio || "").toUpperCase() === "SOUZA";
    const isGuarita = (l.tipo_romaneio || "").toUpperCase() === "RETIRADA_GUARITA";
    const isTotal = (l.tipo_romaneio || "").toUpperCase().includes("TOTAL");

    document.getElementById("modalListaTitulo").textContent = isGuarita ? "Lista de Retiradas - Guarita" : isSouza 
      ? `🚚 Romaneio de Entrega Roberto Souza #${l.numero_lista}` 
      : isTotal
      ? `⚡ Manifesto de Coleta Total Express #${l.numero_lista}`
      : `📋 Detalhes da Lista de Postagem #${l.numero_lista}`;

    const freteTotal = Number(l.valor_total_frete || 0).toFixed(2);
    document.getElementById("modalListaCabecalhoInfo").innerHTML = `
      <div><strong>Tipo:</strong> ${l.tipo_romaneio || 'CORREIOS'}</div>
      <div><strong>Data Geração:</strong> ${l.data_geracao || '-'}</div>
      <div><strong>Qtd. Entregas:</strong> ${l.quantidade_objetos || itens.length}</div>
      <div><strong>Total Fretes:</strong> <span style="color: #10b981; font-weight: 700;">R$ ${freteTotal}</span></div>
      <div><strong>Status:</strong> ${l.status || 'GERADA'}</div>
    `;

    const tbody = document.getElementById("tableBodyModalListaItens");
    if (tbody) {
      tbody.innerHTML = itens.map((it, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${it.servico || '-'}</td>
          <td><strong>${it.codigo_objeto || '-'}</strong></td>
          <td>${it.cep || '-'}</td>
          <td>${it.numero_nf || it.pedido || '-'}</td>
          <td>
            <div>${it.destinatario || '-'}</div>
            ${it.observacoes_entrega ? `<div style="font-size: 0.72rem; color: #f59e0b;">Obs: ${it.observacoes_entrega}</div>` : ''}
          </td>
        </tr>
      `).join("");
    }

    const btnPdf = document.getElementById("btnBaixarPdfModalLista");
    if (btnPdf) {
      btnPdf.onclick = () => isGuarita ? gerarPdfListaRetiradaGuarita(l, itens) : (isSouza ? gerarPdfRomaneioSouza(l, itens) : (isTotal ? gerarPdfRomaneioTotalExpress(l, itens) : gerarPdfPlpOficial(l, itens)));
    }

    modal.style.display = "flex";
  } catch (err) {
    alert(`Erro ao abrir lista: ${err.message}`);
  }
}

async function gerarPdfListaRetiradaGuarita(lista, itens) {
  const { PDFDocument, StandardFonts, rgb } = PDFLib;
  const pdf = await PDFDocument.create();
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const W = 595.28, H = 841.89;
  let page = pdf.addPage([W, H]);
  let y = 112;
  const text = (value, x, top, size = 9, f = font, color = rgb(0.12, 0.16, 0.22)) => page.drawText(sanitizeWinAnsi(value), { x, y: H - top - size, size, font: f, color, maxWidth: W - x - 36 });
  const heading = ["#", "Pedido / NF", "Destinatario", "Observacoes", "Ponto", "OK"];
  const cols = [36, 70, 160, 280, 470, 525];
  page.drawRectangle({ x: 30, y: H - 30 - 62, width: W - 60, height: 62, color: rgb(0.08, 0.16, 0.22) });
  text("COMUNIDADE CATOLICA SHALOM", 44, 42, 13, bold, rgb(1, 1, 1));
  text("LISTA DE CONFERENCIA - RETIRADAS NA GUARITA", 44, 63, 10, bold, rgb(0.45, 0.86, 0.98));
  text(`Lista: ${lista.numero_lista || "-"}    Gerada: ${lista.data_geracao || "-"}    Operador: ${lista.usuario_geracao || "-"}`, 36, 92, 8);
  const drawHeader = () => {
    page.drawRectangle({ x: 32, y: H - y - 22, width: W - 64, height: 22, color: rgb(0.88, 0.92, 0.95) });
    heading.forEach((label, i) => text(label, cols[i], y + 6, 7, bold));
    y += 22;
  };
  drawHeader();
  for (let i = 0; i < (itens || []).length; i++) {
    if (y > H - 74) { page = pdf.addPage([W, H]); y = 48; drawHeader(); }
    const item = itens[i];
    page.drawRectangle({ x: 32, y: H - y - 36, width: W - 64, height: 36, borderColor: rgb(0.78, 0.82, 0.86), borderWidth: 0.5 });
    text(String(i + 1), cols[0], y + 7, 8, bold);
    text(`${item.pedido || "-"}${item.numero_nf ? ` / NF ${item.numero_nf}` : ""}`, cols[1], y + 7, 7);
    text(String(item.destinatario || "-").slice(0, 28), cols[2], y + 7, 7);
    text(String(item.observacoes_entrega || "").slice(0, 38) || "-", cols[3], y + 7, 7);
    text("GUARITA", cols[4], y + 7, 7, bold);
    page.drawRectangle({ x: cols[5], y: H - y - 23, width: 12, height: 12, borderColor: rgb(0.25, 0.3, 0.35), borderWidth: 0.8 });
    y += 36;
  }
  y += 18;
  if (y > H - 80) { page = pdf.addPage([W, H]); y = 60; }
  page.drawLine({ start: { x: 36, y: H - y }, end: { x: W - 36, y: H - y }, thickness: 0.8, color: rgb(0.3, 0.35, 0.4) });
  text("Conferente: ____________________________________    Data/Hora: __________________", 36, y + 10, 8, bold);
  imprimirPdfBase64(base64ArrayBuffer(await pdf.save()));
}

async function gerarPdfRomaneioSouza(lista, itens) {
  const { PDFDocument, StandardFonts, rgb } = PDFLib;
  const pdfDoc = await PDFDocument.create();

  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  const ITENS_POR_PAGINA = 24;
  const totalPaginas = Math.max(1, Math.ceil(itens.length / ITENS_POR_PAGINA));

  const hoje = new Date();
  const dataHojeFmt = hoje.toLocaleDateString("pt-BR") + " " + hoje.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  let dataGeracaoFmt = dataHojeFmt;
  if (lista.data_geracao) {
    const raw = String(lista.data_geracao).replace("T", " ").trim();
    const [dPart, tPart] = raw.split(" ");
    if (dPart && dPart.includes("-")) {
      const dp = dPart.split("-");
      dataGeracaoFmt = `${dp[2]}/${dp[1]}/${dp[0]}` + (tPart ? ` ${tPart.substring(0,5)}` : "");
    } else {
      dataGeracaoFmt = raw.substring(0, 16);
    }
  }
  const numLista = lista.numero_lista || "000000";
  const valorTotalGeral = Number(lista.valor_total_frete || 0).toFixed(2);

  for (let pag = 0; pag < totalPaginas; pag++) {
    const page = pdfDoc.addPage([595.28, 841.89]); // A4 Retrato
    const W = 595.28;
    const H = 841.89;

    const drawText = (textStr, options) => {
      const ptX = options.x;
      const ptY = H - options.yTop - (options.size || 8);
      page.drawText(sanitizeWinAnsi(textStr), { ...options, x: ptX, y: ptY });
    };

    const drawRect = (options) => {
      const ptX = options.x;
      const ptW = options.w;
      const ptH = options.h;
      const ptY = H - options.yTop - ptH;
      page.drawRectangle({
        x: ptX,
        y: ptY,
        width: ptW,
        height: ptH,
        color: options.color,
        borderColor: options.borderColor,
        borderWidth: options.borderWidth || 0
      });
    };

    const drawLine = (x1, yTop1, x2, yTop2, thickness = 0.5, color = rgb(0,0,0)) => {
      page.drawLine({
        start: { x: x1, y: H - yTop1 },
        end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
        thickness: thickness,
        color: color
      });
    };

    // 1. QUADRO SUPERIOR DO CABEÇALHO (PADRÃO LISTA DE POSTAGEM / ROMANEIO)
    drawRect({ x: 30, yTop: 30, w: W - 60, h: 65, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(180, 30, 180, 95, 1);
    drawLine(410, 30, 410, 95, 1);

    // Coluna 1: Nome da Transportadora / Motorista
    drawText("ROBERTO SOUZA", { x: 42, yTop: 50, size: 13, font: fontBold, color: rgb(0.05, 0.25, 0.6) });
    drawText("ENTREGA LOCAL / EXPRESSA", { x: 42, yTop: 66, size: 7.5, font: fontBold, color: rgb(0.3, 0.3, 0.3) });

    // Coluna 2: LISTA DE POSTAGEM / ROMANEIO DE ENTREGAS
    drawText("LISTA DE POSTAGEM", { x: 215, yTop: 52, size: 14, font: fontBold, color: rgb(0,0,0) });
    drawText("ROMANEIO DE ENTREGA LOCAL", { x: 198, yTop: 72, size: 10.5, font: fontBold, color: rgb(0.1, 0.1, 0.1) });

    // Coluna 3: Metadados (Espaçamento e alinhamento ajustados sem sobreposição)
    drawText(`DATA GERAÇÃO: ${dataGeracaoFmt}`, { x: 416, yTop: 43, size: 7.2, font: fontBold });
    drawText(`Nº LISTA: ${numLista}`, { x: 416, yTop: 55, size: 7.2, font: fontBold });
    drawText(`FOLHA: ${pag + 1}/${totalPaginas}`, { x: 518, yTop: 55, size: 7.2, font: fontBold });
    drawText(`DATA IMPRESSÃO: ${dataHojeFmt}`, { x: 416, yTop: 72, size: 7.0, font: fontReg });

    // 2. QUADRO DADOS DO CLIENTE / EMITENTE (Altura expandida de 25 para 30 pt para não cortar o texto)
    drawRect({ x: 30, yTop: 95, w: W - 60, h: 30, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("NOME DO CLIENTE", { x: 35, yTop: 101, size: 6.5, font: fontBold });
    drawText("ASSOCIACAO SHALOM", { x: 35, yTop: 114, size: 9.5, font: fontBold });
    drawText("CNPJ 07044456000100", { x: 420, yTop: 112, size: 8.5, font: fontBold });

    // 3. QUADRO RESUMO DO MOTORISTA E VALOR TOTAL DO FRETE
    drawRect({ x: 30, yTop: 125, w: W - 60, h: 32, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(300, 125, 300, 157, 1);

    drawText("MOTORISTA / TRANSPORTADOR", { x: 35, yTop: 132, size: 6.5, font: fontBold });
    drawText("ROBERTO SOUZA (ENTREGA PRÓPRIA)", { x: 35, yTop: 145, size: 9, font: fontBold });

    drawText("VALOR TOTAL DOS FRETES A PAGAR", { x: 310, yTop: 132, size: 6.5, font: fontBold });
    drawText(`R$ ${valorTotalGeral}`, { x: 310, yTop: 145, size: 10, font: fontBold, color: rgb(0.05, 0.5, 0.2) });

    // 4. CABEÇALHO DA TABELA DE OBJETOS
    let yTabela = 163;
    drawRect({ x: 30, yTop: yTabela, w: W - 60, h: 16, color: rgb(0.96, 0.96, 0.96), borderColor: rgb(0,0,0), borderWidth: 1 });
    
    drawText("N.", { x: 33, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Serviço", { x: 50, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Nº do Objeto", { x: 120, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("CEP", { x: 200, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Frete (R$)", { x: 250, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("N.F. / Ped", { x: 300, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Destinatário", { x: 360, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Bairro / Cidade", { x: 480, yTop: yTabela + 4, size: 7.2, font: fontBold });

    // Linhas de itens
    yTabela += 16;
    const inicioIdx = pag * ITENS_POR_PAGINA;
    const fimIdx = Math.min(itens.length, inicioIdx + ITENS_POR_PAGINA);

    for (let i = inicioIdx; i < fimIdx; i++) {
      const it = itens[i];
      const cepRaw = String(it.cep || "").replace(/\D/g, "");
      const cepFmt = cepRaw.length === 8 ? `${cepRaw.substring(0,5)}-${cepRaw.substring(5)}` : (it.cep || "-");
      const nfPedStr = it.numero_nf ? String(it.numero_nf) : (it.pedido ? `#${it.pedido}` : "-");
      const destStr = String(it.destinatario || "").substring(0, 24);
      const freteFmt = Number(it.valor_frete || 11.50).toFixed(2);
      const bairroCid = `${(it.bairro || '').substring(0, 11)} / ${(it.cidade || 'FOR').substring(0, 7)}`;

      drawText(String(i + 1), { x: 33, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText("SOUZA", { x: 50, yTop: yTabela + 3, size: 6.8, font: fontBold });
      drawText(it.codigo_objeto || "-", { x: 120, yTop: yTabela + 3, size: 7.2, font: fontBold });
      drawText(cepFmt, { x: 200, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(`R$ ${freteFmt}`, { x: 250, yTop: yTabela + 3, size: 6.8, font: fontBold, color: rgb(0.05, 0.5, 0.2) });
      drawText(nfPedStr.substring(0, 12), { x: 300, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(destStr, { x: 360, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(bairroCid, { x: 480, yTop: yTabela + 3, size: 6.8, font: fontReg });

      drawLine(30, yTabela + 14, W - 30, yTabela + 14, 0.3, rgb(0.8, 0.8, 0.8));
      yTabela += 14;
    }

    // 5. RODAPÉ DE TERMO E ASSINATURAS (PADRÃO LISTA DE POSTAGEM)
    const yRodape = H - 145;
    drawRect({ x: 30, yTop: yRodape, w: W - 60, h: 22, color: rgb(0.96, 0.96, 0.96), borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("TOTAL DE OBJETOS", { x: 35, yTop: yRodape + 4, size: 8, font: fontBold });
    drawText(String(itens.length), { x: 140, yTop: yRodape + 4, size: 9, font: fontBold });
    drawText("TOTAL FRETE: R$ " + valorTotalGeral, { x: 200, yTop: yRodape + 4, size: 8.5, font: fontBold, color: rgb(0.05, 0.5, 0.2) });
    drawText("ASSOCIACAO SHALOM", { x: 420, yTop: yRodape + 4, size: 8, font: fontBold });

    // Quadro de assinaturas com 3 colunas
    const yAssin = yRodape + 22;
    drawRect({ x: 30, yTop: yAssin, w: W - 60, h: 90, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(175, yAssin, 175, yAssin + 90, 1);
    drawLine(360, yAssin, 360, yAssin + 90, 1);
    drawLine(175, yAssin + 45, 360, yAssin + 45, 1);

    // Box 1: Visto Expedição
    drawText("EXPEDIÇÃO SHALOM - VISTO / CARIMBO", { x: 35, yTop: yAssin + 6, size: 6.5, font: fontBold });

    // Box 2: Contratante
    drawText("CONTRATANTE - ASSINATURA/NOME LEGÍVEL", { x: 180, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText(`Declaro que entreguei ${itens.length} objetos para transporte.`, { x: 180, yTop: yAssin + 22, size: 7.5, font: fontBold });

    // Box 3: Motorista Coletor
    drawText("ROBERTO SOUZA - ASSINATURA MOTORISTA COLETOR", { x: 180, yTop: yAssin + 52, size: 6.5, font: fontBold });

    // Box 4: Conferência
    drawText("NÚMERO DO DOCUMENTO / DATA", { x: 365, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText("CONFERÊNCIA FINAL / RECEBIMENTO", { x: 365, yTop: yAssin + 52, size: 6.5, font: fontBold });
  }

  const bytes = await pdfDoc.save();
  imprimirPdfBase64(base64ArrayBuffer(bytes));
}

async function gerarPdfRomaneioTotalExpress(lista, itens) {
  const { PDFDocument, StandardFonts, rgb } = PDFLib;
  const pdfDoc = await PDFDocument.create();

  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  const ITENS_POR_PAGINA = 24;
  const totalPaginas = Math.max(1, Math.ceil(itens.length / ITENS_POR_PAGINA));

  const hoje = new Date();
  const dataHojeFmt = hoje.toLocaleDateString("pt-BR") + " " + hoje.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  let dataGeracaoFmt = dataHojeFmt;
  if (lista.data_geracao) {
    const raw = String(lista.data_geracao).replace("T", " ").trim();
    const [dPart, tPart] = raw.split(" ");
    if (dPart && dPart.includes("-")) {
      const dp = dPart.split("-");
      dataGeracaoFmt = `${dp[2]}/${dp[1]}/${dp[0]}` + (tPart ? ` ${tPart.substring(0,5)}` : "");
    } else {
      dataGeracaoFmt = raw.substring(0, 16);
    }
  }
  const numLista = lista.numero_lista || "000000";

  for (let pag = 0; pag < totalPaginas; pag++) {
    const page = pdfDoc.addPage([595.28, 841.89]); // A4 Retrato
    const W = 595.28;
    const H = 841.89;

    const drawText = (textStr, options) => {
      const ptX = options.x;
      const ptY = H - options.yTop - (options.size || 8);
      page.drawText(sanitizeWinAnsi(textStr), { ...options, x: ptX, y: ptY });
    };

    const drawRect = (options) => {
      const ptX = options.x;
      const ptW = options.w;
      const ptH = options.h;
      const ptY = H - options.yTop - ptH;
      page.drawRectangle({
        x: ptX,
        y: ptY,
        width: ptW,
        height: ptH,
        color: options.color,
        borderColor: options.borderColor,
        borderWidth: options.borderWidth || 0
      });
    };

    const drawLine = (x1, yTop1, x2, yTop2, thickness = 0.5, color = rgb(0,0,0)) => {
      page.drawLine({
        start: { x: x1, y: H - yTop1 },
        end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
        thickness: thickness,
        color: color
      });
    };

    // 1. CABEÇALHO SUPERIOR TOTAL EXPRESS
    drawRect({ x: 30, yTop: 30, w: W - 60, h: 65, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(180, 30, 180, 95, 1);
    drawLine(410, 30, 410, 95, 1);

    // Coluna 1: Total Express
    drawText("TOTAL EXPRESS", { x: 42, yTop: 50, size: 14, font: fontBold, color: rgb(0, 0, 0) });
    drawText("COLETA & ENCOMENDAS", { x: 42, yTop: 66, size: 7.5, font: fontBold, color: rgb(0.3, 0.3, 0.3) });

    // Coluna 2: MANIFESTO DE COLETA
    drawText("MANIFESTO DE COLETA", { x: 200, yTop: 52, size: 14, font: fontBold, color: rgb(0,0,0) });
    drawText("TOTAL EXPRESS - ROMANEIO DE CARGA", { x: 195, yTop: 72, size: 9.5, font: fontBold, color: rgb(0.2, 0.2, 0.2) });

    // Coluna 3: Metadados
    drawText(`DATA GERAÇÃO: ${dataGeracaoFmt}`, { x: 416, yTop: 43, size: 7.2, font: fontBold });
    drawText(`MANIFESTO Nº: ${numLista}`, { x: 416, yTop: 55, size: 7.2, font: fontBold });
    drawText(`FOLHA: ${pag + 1}/${totalPaginas}`, { x: 518, yTop: 55, size: 7.2, font: fontBold });
    drawText(`DATA IMPRESSÃO: ${dataHojeFmt}`, { x: 416, yTop: 72, size: 7.0, font: fontReg });

    // 2. DADOS DO CLIENTE / REMETENTE
    drawRect({ x: 30, yTop: 95, w: W - 60, h: 30, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("REMETENTE / CONTRATANTE", { x: 35, yTop: 101, size: 6.5, font: fontBold });
    drawText("EDICOES SHALOM / ASSOCIACAO SHALOM", { x: 35, yTop: 114, size: 9.5, font: fontBold });
    drawText("CNPJ: 07.044.456/0003-64", { x: 410, yTop: 104, size: 7.5, font: fontBold });
    drawText("AQUIRAZ - CE (61700-000)", { x: 410, yTop: 115, size: 7.5, font: fontReg });

    // 3. TABELA DE ENCOMENDAS
    let yTabela = 135;
    drawRect({ x: 30, yTop: yTabela, w: W - 60, h: 16, color: rgb(0.94, 0.94, 0.94), borderColor: rgb(0,0,0), borderWidth: 1 });

    drawText("N.", { x: 33, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("AWB / Rastreio", { x: 52, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Serviço", { x: 145, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("N.F. / Pedido", { x: 190, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Destinatário", { x: 260, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("CEP", { x: 395, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Cidade / UF", { x: 450, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Rota", { x: 535, yTop: yTabela + 4, size: 7.2, font: fontBold });

    // Linhas de itens
    yTabela += 16;
    const inicioIdx = pag * ITENS_POR_PAGINA;
    const fimIdx = Math.min(itens.length, inicioIdx + ITENS_POR_PAGINA);

    for (let i = inicioIdx; i < fimIdx; i++) {
      const it = itens[i];
      const cepRaw = String(it.cep || "").replace(/\D/g, "");
      const cepFmt = cepRaw.length === 8 ? `${cepRaw.substring(0,5)}-${cepRaw.substring(5)}` : (it.cep || "-");
      const nfPedStr = it.numero_nf ? `NF ${it.numero_nf}` : (it.pedido ? `Ped ${it.pedido}` : "-");
      const destStr = String(it.destinatario || "").substring(0, 22);
      const servStr = (it.servico || "EXP").replace("TOTAL_EXPRESS", "EXP");
      const cidUf = `${(it.cidade || '').substring(0, 10)} / ${(it.uf || '')}`;
      const rotaStr = (it.rota || it.observacoes_entrega || "-").substring(0, 10);

      drawText(String(i + 1), { x: 33, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(it.codigo_objeto || "-", { x: 52, yTop: yTabela + 3, size: 7.2, font: fontBold });
      drawText(servStr, { x: 145, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(nfPedStr, { x: 190, yTop: yTabela + 3, size: 6.8, font: fontBold });
      drawText(destStr, { x: 260, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(cepFmt, { x: 395, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(cidUf, { x: 450, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(rotaStr, { x: 535, yTop: yTabela + 3, size: 6.8, font: fontBold });

      drawLine(30, yTabela + 14, W - 30, yTabela + 14, 0.3, rgb(0.8, 0.8, 0.8));
      yTabela += 14;
    }

    // 4. RODAPÉ DE TERMO E ASSINATURAS TOTAL EXPRESS
    const yRodape = H - 145;
    drawRect({ x: 30, yTop: yRodape, w: W - 60, h: 22, color: rgb(0.96, 0.96, 0.96), borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("TOTAL DE VOLUMES / ENCOMENDAS:", { x: 35, yTop: yRodape + 4, size: 8, font: fontBold });
    drawText(String(itens.length), { x: 195, yTop: yRodape + 4, size: 9, font: fontBold });
    drawText("TOTAL EXPRESS - LOGÍSTICA E DISTRIBUIÇÃO", { x: 330, yTop: yRodape + 4, size: 8, font: fontBold });

    // Quadro de assinaturas com 3 colunas
    const yAssin = yRodape + 22;
    drawRect({ x: 30, yTop: yAssin, w: W - 60, h: 90, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(195, yAssin, 195, yAssin + 90, 1);
    drawLine(380, yAssin, 380, yAssin + 90, 1);

    // Box 1: Expedição Shalom
    drawText("EXPEDIÇÃO SHALOM - RESPONSÁVEL", { x: 35, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText(`Entregue ${itens.length} volume(s) à Total Express.`, { x: 35, yTop: yAssin + 24, size: 7.5, font: fontBold });
    drawLine(35, yAssin + 65, 185, yAssin + 65, 0.5, rgb(0.5, 0.5, 0.5));
    drawText("Assinatura do Expedidor", { x: 35, yTop: yAssin + 70, size: 6.5, font: fontReg });

    // Box 2: Motorista Coletor Total Express
    drawText("MOTORISTA / COLETOR TOTAL EXPRESS", { x: 202, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText("Nome legível: _______________________________", { x: 202, yTop: yAssin + 24, size: 6.8, font: fontReg });
    drawText("RG / CPF: ___________________________________", { x: 202, yTop: yAssin + 42, size: 6.8, font: fontReg });
    drawText("Placa do Veículo: ___________________________", { x: 202, yTop: yAssin + 60, size: 6.8, font: fontReg });
    drawText("Assinatura: _________________________________", { x: 202, yTop: yAssin + 78, size: 6.8, font: fontReg });

    // Box 3: Data / Hora e Carimbo
    drawText("DATA E HORA DA COLETA", { x: 388, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText(`Data: ____/____/________   Hora: ____:____`, { x: 388, yTop: yAssin + 30, size: 7.2, font: fontBold });
    drawText("Visto / Carimbo Base Total Express:", { x: 388, yTop: yAssin + 55, size: 6.5, font: fontReg });
  }

  const bytes = await pdfDoc.save();
  imprimirPdfBase64(base64ArrayBuffer(bytes));
}


// =========================================================================
// LOCAIS RECORRENTES E COTAÇÃO FRENET PARA ENTRADA AVULSA (SOUZA)
// =========================================================================
const STORAGE_KEY_LOCAIS_AVULSOS = "gestao_entregas_locais_avulsos_v1";

function carregarLocaisAvulsosSalvos() {
  const sel = document.getElementById("abaAvulsaLocaisSalvos");
  if (!sel) return;
  try {
    const salvos = JSON.parse(localStorage.getItem(STORAGE_KEY_LOCAIS_AVULSOS) || "[]");
    sel.innerHTML = `<option value="">⭐ Carregar Local Recorrente Salvo (${salvos.length})...</option>` +
      salvos.map((loc, idx) => `<option value="${idx}">${loc.nome} - ${loc.bairro || 'Fortaleza'}</option>`).join("");
  } catch (e) {
    console.error("Erro ao carregar locais salvos:", e);
  }
}

function salvarLocalAvulsoRecorrente(dados) {
  try {
    let salvos = JSON.parse(localStorage.getItem(STORAGE_KEY_LOCAIS_AVULSOS) || "[]");
    const idxExistente = salvos.findIndex(s => (s.nome || "").toLowerCase().trim() === (dados.nome || "").toLowerCase().trim());
    if (idxExistente >= 0) {
      salvos[idxExistente] = dados;
    } else {
      salvos.unshift(dados);
      if (salvos.length > 30) salvos = salvos.slice(0, 30);
    }
    localStorage.setItem(STORAGE_KEY_LOCAIS_AVULSOS, JSON.stringify(salvos));
    carregarLocaisAvulsosSalvos();
  } catch (e) {
    console.error("Erro ao salvar local recorrente:", e);
  }
}

function selecionarLocalAvulsoSalvo(idxVal) {
  if (idxVal === "") return;
  try {
    const salvos = JSON.parse(localStorage.getItem(STORAGE_KEY_LOCAIS_AVULSOS) || "[]");
    const loc = salvos[parseInt(idxVal, 10)];
    if (!loc) return;

    if (document.getElementById("abaAvulsaDescricao")) document.getElementById("abaAvulsaDescricao").value = loc.descricao || "";
    if (document.getElementById("abaAvulsaDestinatario")) document.getElementById("abaAvulsaDestinatario").value = loc.nome || "";
    if (document.getElementById("abaAvulsaEndereco")) document.getElementById("abaAvulsaEndereco").value = loc.endereco || "";
    if (document.getElementById("abaAvulsaBairro")) document.getElementById("abaAvulsaBairro").value = loc.bairro || "";
    if (document.getElementById("abaAvulsaCidade")) document.getElementById("abaAvulsaCidade").value = loc.cidade || "Fortaleza / CE";
    if (document.getElementById("abaAvulsaCep")) document.getElementById("abaAvulsaCep").value = loc.cep || "";
    if (document.getElementById("abaAvulsaValorFrete")) document.getElementById("abaAvulsaValorFrete").value = loc.frete || 11.50;
    if (document.getElementById("abaAvulsaObs")) document.getElementById("abaAvulsaObs").value = loc.obs || "";
    if (loc.peso && document.getElementById("abaAvulsaPeso")) document.getElementById("abaAvulsaPeso").value = loc.peso;
  } catch (e) {
    console.error("Erro ao preencher local salvo:", e);
  }
}
window.selecionarLocalAvulsoSalvo = selecionarLocalAvulsoSalvo;

async function cotarFreteAvulsoFrenet() {
  const cep = (document.getElementById("abaAvulsaCep")?.value || "").replace(/\D/g, "");
  const peso = parseFloat(document.getElementById("abaAvulsaPeso")?.value) || 1.0;
  const btn = document.getElementById("btnCotarAvulsoFrenet");

  if (!cep || cep.length !== 8) {
    alert("Informe um CEP válido com 8 dígitos para cotar na Frenet.");
    return;
  }

  const origText = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Cotando..."; }

  try {
    const res = await fetch(`/api/frenet/cotar?cep=${cep}&peso=${peso}&valor=100`);
    const data = await safeFetchJson(res);
    const cotacoes = data.cotacoes || [];
    if (cotacoes.length === 0) {
      alert("Nenhuma cotação retornada pela Frenet para este CEP. Mantendo valor padrão R$ 11,50.");
      return;
    }

    let sel = cotacoes.find(c => {
      const s = (c.servico || "").toUpperCase();
      const t = (c.transportadora || "").toUpperCase();
      return s.includes("ECON") || s.includes("SOUZA") || t.includes("SOUZA") || t.includes("PERSONALIZADA");
    });
    if (!sel) sel = cotacoes[0];

    const valFrete = parseFloat(sel.valor !== undefined ? sel.valor : (sel.preco || 11.50)) || 11.50;
    if (document.getElementById("abaAvulsaValorFrete")) {
      document.getElementById("abaAvulsaValorFrete").value = valFrete.toFixed(2);
      document.getElementById("abaAvulsaValorFrete").style.background = "rgba(16, 185, 129, 0.15)";
    }
    alert(`⚡ Frete cotado na Frenet com sucesso: R$ ${valFrete.toFixed(2)} (${sel.servico || sel.transportadora || 'Entrega Local'})`);
  } catch (err) {
    alert(`Erro ao cotar frete na Frenet: ${err.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = origText; }
  }
}
window.cotarFreteAvulsoFrenet = cotarFreteAvulsoFrenet;


async function gerarPdfPlpOficial(lista, itens) {
  const { PDFDocument, StandardFonts, rgb } = PDFLib;
  const pdfDoc = await PDFDocument.create();

  const fontBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
  const fontReg = await pdfDoc.embedFont(StandardFonts.Helvetica);

  const ITENS_POR_PAGINA = 24;
  const totalPaginas = Math.max(1, Math.ceil(itens.length / ITENS_POR_PAGINA));

  const hoje = new Date();
  const dataHojeFmt = hoje.toLocaleDateString("pt-BR") + " " + hoje.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  let dataGeracaoFmt = dataHojeFmt;
  if (lista.data_geracao) {
    const raw = String(lista.data_geracao).replace("T", " ").trim();
    const [dPart, tPart] = raw.split(" ");
    if (dPart && dPart.includes("-")) {
      const dp = dPart.split("-");
      dataGeracaoFmt = `${dp[2]}/${dp[1]}/${dp[0]}` + (tPart ? ` ${tPart.substring(0,5)}` : "");
    } else {
      dataGeracaoFmt = raw.substring(0, 16);
    }
  }
  const numLista = lista.numero_lista || "000000";

  for (let pag = 0; pag < totalPaginas; pag++) {
    const page = pdfDoc.addPage([595.28, 841.89]); // A4 Retrato
    const W = 595.28;
    const H = 841.89;

    const drawText = (text, options) => {
      const ptX = options.x;
      const ptY = H - options.yTop - (options.size || 8);
      page.drawText(sanitizeWinAnsi(text), { ...options, x: ptX, y: ptY });
    };

    const drawRect = (options) => {
      const ptX = options.x;
      const ptW = options.w;
      const ptH = options.h;
      const ptY = H - options.yTop - ptH;
      page.drawRectangle({
        x: ptX,
        y: ptY,
        width: ptW,
        height: ptH,
        color: options.color,
        borderColor: options.borderColor,
        borderWidth: options.borderWidth || 0
      });
    };

    const drawLine = (x1, yTop1, x2, yTop2, thickness = 0.5, color = rgb(0,0,0)) => {
      page.drawLine({
        start: { x: x1, y: H - yTop1 },
        end: { x: x2, y: yTop2 === yTop1 ? H - yTop1 : H - yTop2 },
        thickness: thickness,
        color: color
      });
    };

    const drawBarcode = async (options, x, yTop, w, h) => {
      try {
        const canvas = document.createElement("canvas");
        bwipjs.toCanvas(canvas, options);
        const pngUrl = canvas.toDataURL("image/png");
        const pngImageBytes = await fetch(pngUrl).then(res => res.arrayBuffer());
        const pngImage = await pdfDoc.embedPng(pngImageBytes);
        page.drawImage(pngImage, { x: x, y: H - yTop - h, width: w, height: h });
      } catch (eBar) {
        console.error("Erro ao gerar barcode PLP Correios:", eBar);
      }
    };

    // 1. QUADRO SUPERIOR DO CABEÇALHO OFICIAL CORREIOS
    drawRect({ x: 30, yTop: 30, w: W - 60, h: 65, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(180, 30, 180, 95, 1);
    drawLine(410, 30, 410, 95, 1);

    // Coluna 1: Logo Correios / Título
    drawText("Correios", { x: 50, yTop: 54, size: 22, font: fontBold, color: rgb(0.05, 0.25, 0.6) });

    // Coluna 2: LISTA DE POSTAGEM A FATURAR
    drawText("LISTA DE POSTAGEM", { x: 215, yTop: 52, size: 14, font: fontBold, color: rgb(0,0,0) });
    drawText("A FATURAR", { x: 250, yTop: 72, size: 13, font: fontBold, color: rgb(0,0,0) });

    // Coluna 3: Metadados (Ajustado sem sobreposição)
    drawText(`DATA GERAÇÃO: ${dataGeracaoFmt}`, { x: 416, yTop: 43, size: 7.2, font: fontBold });
    drawText(`Nº LISTA: ${numLista}`, { x: 416, yTop: 55, size: 7.2, font: fontBold });
    drawText(`FOLHA: ${pag + 1}/${totalPaginas}`, { x: 518, yTop: 55, size: 7.2, font: fontBold });
    drawText(`DATA IMPRESSÃO: ${dataHojeFmt}`, { x: 416, yTop: 72, size: 7.0, font: fontReg });

    // 2. QUADRO DADOS DO CLIENTE (Altura ajustada para 30 pt para não sobrepor texto e linha)
    drawRect({ x: 30, yTop: 95, w: W - 60, h: 30, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("NOME DO CLIENTE", { x: 35, yTop: 101, size: 6.5, font: fontBold });
    drawText("ASSOCIACAO SHALOM", { x: 35, yTop: 114, size: 9.5, font: fontBold });
    drawText("CNPJ 07044456000100", { x: 420, yTop: 112, size: 8.5, font: fontBold });

    // 3. QUADRO CONTRATO & CARTÃO COM CÓDIGOS DE BARRA
    drawRect({ x: 30, yTop: 125, w: W - 60, h: 42, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(190, 120, 190, 162, 1);

    drawText("Nº DO CONTRATO", { x: 35, yTop: 127, size: 6.5, font: fontBold });
    drawText(lista.contrato || "9912293215", { x: 35, yTop: 140, size: 9, font: fontBold });
    await drawBarcode({
      bcid: 'code128',
      text: lista.contrato || "9912293215",
      scale: 2,
      height: 12,
      includetext: false
    }, 95, 126, 85, 28);

    drawText("Nº CARTÃO DE POSTAGEM", { x: 195, yTop: 127, size: 6.5, font: fontBold });
    drawText(lista.cartao_postagem || "66578957", { x: 195, yTop: 140, size: 9, font: fontBold });
    await drawBarcode({
      bcid: 'code128',
      text: lista.cartao_postagem || "66578957",
      scale: 2,
      height: 12,
      includetext: false
    }, 285, 126, 95, 28);

    // 4. CABEÇALHO DA TABELA DE OBJETOS
    let yTabela = 168;
    drawRect({ x: 30, yTop: yTabela, w: W - 60, h: 16, color: rgb(0.96, 0.96, 0.96), borderColor: rgb(0,0,0), borderWidth: 1 });
    
    drawText("N.", { x: 33, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Serviço", { x: 50, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Nº do Objeto", { x: 130, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("CEP", { x: 215, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("VD (R$)", { x: 265, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("ADIC.", { x: 310, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("VC (R$)", { x: 345, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("N.F.", { x: 382, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Destinatário", { x: 425, yTop: yTabela + 4, size: 7.2, font: fontBold });
    drawText("Cartão Post.", { x: 512, yTop: yTabela + 4, size: 7.2, font: fontBold });

    // Linhas de itens
    yTabela += 16;
    const inicioIdx = pag * ITENS_POR_PAGINA;
    const fimIdx = Math.min(itens.length, inicioIdx + ITENS_POR_PAGINA);

    for (let i = inicioIdx; i < fimIdx; i++) {
      const it = itens[i];
      const srvRaw = (it.servico || "PAC").toUpperCase();
      let srvDesc = srvRaw;
      if (srvRaw.includes("MODICO") || srvRaw.includes("MÓDICO") || srvRaw === "20133") srvDesc = "20133 IMPRESSO";
      else if (srvRaw.includes("SEDEX")) srvDesc = "3220 SEDEX";
      else if (srvRaw.includes("PAC")) srvDesc = "3298 PAC";
      else if (srvRaw.includes("MINI")) srvDesc = "4227 MINI ENVIOS";

      const cepRaw = String(it.cep || "").replace(/\D/g, "");
      const cepFmt = cepRaw.length === 8 ? `${cepRaw.substring(0,5)}-${cepRaw.substring(5)}` : (it.cep || "");
      const nfStr = it.numero_nf ? String(it.numero_nf) : "-";
      const destStr = String(it.destinatario || "").substring(0, 18);
      const cartaoStr = `${lista.cartao_postagem || "66578957"}/`;

      drawText(String(i + 1), { x: 33, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(srvDesc.substring(0, 15), { x: 50, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(it.codigo_objeto || "-", { x: 130, yTop: yTabela + 3, size: 7.2, font: fontBold });
      drawText(cepFmt, { x: 215, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText("-", { x: 275, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText("RM", { x: 315, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText("0.0", { x: 350, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(nfStr, { x: 382, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(destStr, { x: 425, yTop: yTabela + 3, size: 6.8, font: fontReg });
      drawText(cartaoStr, { x: 512, yTop: yTabela + 3, size: 6.8, font: fontReg });

      drawLine(30, yTabela + 14, W - 30, yTabela + 14, 0.3, rgb(0.8, 0.8, 0.8));
      yTabela += 14;
    }

    // 5. RODAPÉ DE TERMO E ASSINATURAS DOS CORREIOS (EM TODAS AS FOLHAS OU NA ÚLTIMA)
    const yRodape = H - 145;
    drawRect({ x: 30, yTop: yRodape, w: W - 60, h: 22, color: rgb(0.96, 0.96, 0.96), borderColor: rgb(0,0,0), borderWidth: 1 });
    drawText("TOTAL", { x: 35, yTop: yRodape + 4, size: 8, font: fontBold });
    drawText(String(itens.length), { x: 260, yTop: yRodape + 4, size: 9, font: fontBold });
    drawText("ASSOCIACAO SHALOM", { x: 35, yTop: yRodape + 13, size: 7.5, font: fontBold });

    // Quadro de assinaturas com 3 colunas
    const yAssin = yRodape + 22;
    drawRect({ x: 30, yTop: yAssin, w: W - 60, h: 90, borderColor: rgb(0,0,0), borderWidth: 1 });
    drawLine(125, yAssin, 125, yAssin + 90, 1);
    drawLine(360, yAssin, 360, yAssin + 90, 1);
    drawLine(125, yAssin + 45, 360, yAssin + 45, 1);

    // Box 1: Carimbo
    drawText("CORREIOS - CARIMBO", { x: 35, yTop: yAssin + 6, size: 6.5, font: fontBold });

    // Box 2: Contratante
    drawText("CONTRATANTE - ASSINATURA/NOME LEGÍVEL", { x: 130, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText(`Declaro que recebi ${itens.length} objetos.`, { x: 130, yTop: yAssin + 22, size: 8, font: fontBold });

    // Box 3: Coletor
    drawText("CORREIOS - ASSINATURA E MATRÍCULA COLETOR", { x: 130, yTop: yAssin + 52, size: 6.5, font: fontBold });

    // Box 4: Conferente / Documento
    drawText("NÚMERO DO DOCUMENTO", { x: 365, yTop: yAssin + 6, size: 6.5, font: fontBold });
    drawText("CORREIOS - ASSINATURA E MATRÍCULA CONFERENTE", { x: 365, yTop: yAssin + 52, size: 6.5, font: fontBold });
  }

  const bytes = await pdfDoc.save();
  imprimirPdfBase64(base64ArrayBuffer(bytes));
}

// ==========================================================================
// APP MOBILE / MODO ENTREGADOR (ROBERTO SOUZA)
// ==========================================================================
let mobileItensAtuais = [];
let mobileListaIdAtual = null;

async function abrirModalMobileMotorista(listaId) {
  mobileListaIdAtual = listaId;
  const modal = document.getElementById("modalMobileMotorista");
  if (!modal) return;
  modal.style.display = "flex";

  const container = document.getElementById("mobileListaEntregas");
  if (container) container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 20px;">Carregando entregas do romaneio #${listaId}...</div>`;

  try {
    const res = await fetch(`/.netlify/functions/lista-postagem?action=get_lista&lista_id=${listaId}`);
    const data = await safeFetchJson(res);
    const l = data.lista || {};
    mobileItensAtuais = data.itens || [];

    if (l.status === 'CANCELADA') {
      if (container) container.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 30px; font-weight: 600;">⚠️ Este romaneio (#${l.numero_lista}) foi CANCELADO e suas entregas foram liberadas de volta para a expedição.</div>`;
      document.getElementById("mobileRomaneioSub").textContent = `Romaneio #${l.numero_lista} • STATUS: CANCELADA`;
      if (document.getElementById("mobileTotalizadorResumo")) {
        document.getElementById("mobileTotalizadorResumo").textContent = `Romaneio Cancelado (0 entregas ativas)`;
      }
      return;
    }

    document.getElementById("mobileRomaneioSub").textContent = `Romaneio #${l.numero_lista} • Criado em ${l.data_geracao || '-'} • Roberto Souza`;
    renderEntregasMobile();
  } catch (err) {
    if (container) container.innerHTML = `<div style="color: #f87171; text-align: center;">Erro: ${err.message}</div>`;
  }
}

function fecharModalMobileMotorista() {
  const modal = document.getElementById("modalMobileMotorista");
  if (modal) modal.style.display = "none";
}

function renderEntregasMobile() {
  const container = document.getElementById("mobileListaEntregas");
  const resumo = document.getElementById("mobileTotalizadorResumo");
  if (!container) return;

  if (mobileItensAtuais.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 30px;">Nenhuma entrega encontrada neste romaneio.</div>`;
    if (resumo) resumo.textContent = "0 Entregas";
    return;
  }

  let totalFrete = 0;
  let finalizadas = 0;

  const html = mobileItensAtuais.map((it, idx) => {
    const st = (it.status_entrega || "EM_COLETA").toUpperCase();
    if (st === "FINALIZADO") finalizadas++;
    totalFrete += Number(it.valor_frete || 11.50);

    const stBadge = st === "FINALIZADO" 
      ? `<span class="badge badge-success">✅ ENTREGUE</span>` 
      : (st === "EM_TRANSPORTE" 
        ? `<span class="badge" style="background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b;">🚚 EM TRANSPORTE</span>`
        : `<span class="badge badge-secondary">📦 EM COLETA</span>`);

    const endFormatado = `${it.logradouro || ''}, ${it.numero || ''} ${it.bairro ? '- ' + it.bairro : ''} - ${it.cidade || 'Fortaleza'}`;
    const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(endFormatado + ' ' + (it.cep || ''))}`;
    const wppUrl = it.telefone_contato ? `https://wa.me/55${it.telefone_contato.replace(/\D/g, '')}` : null;

    return `
      <div style="background: #1e293b; border: 1px solid ${st === 'FINALIZADO' ? '#10b981' : '#334155'}; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong style="color: #f8fafc; font-size: 0.95rem;">${it.codigo_objeto || '-'}</strong>
            <span style="font-size: 0.75rem; color: #94a3b8; margin-left: 6px;">(${it.numero_nf ? 'NF ' + it.numero_nf : 'Ped #' + (it.pedido || '')})</span>
          </div>
          <div>${stBadge}</div>
        </div>
        
        <div>
          <div style="font-weight: 700; color: #38bdf8; font-size: 0.9rem;">${it.destinatario || '-'}</div>
          <div style="font-size: 0.82rem; color: #cbd5e1; margin-top: 2px;">📍 ${endFormatado}</div>
          ${it.observacoes_entrega ? `<div style="font-size: 0.78rem; background: rgba(245,158,11,0.15); border-left: 3px solid #f59e0b; padding: 4px 8px; margin-top: 4px; color: #fde68a;">⚠️ Obs: ${it.observacoes_entrega}</div>` : ''}
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #334155; padding-top: 8px; flex-wrap: wrap; gap: 6px;">
          <div style="font-size: 0.82rem; color: #10b981; font-weight: 700;">Frete: R$ ${Number(it.valor_frete || 11.50).toFixed(2)}</div>
          <div style="display: flex; gap: 6px;">
            <a href="${mapsUrl}" target="_blank" class="btn btn-sm btn-primary" style="padding: 4px 8px; font-size: 0.75rem; text-decoration: none;">🗺️ Rotas Maps</a>
            ${wppUrl ? `<a href="${wppUrl}" target="_blank" class="btn btn-sm" style="background: #16a34a; color: #fff; padding: 4px 8px; font-size: 0.75rem; text-decoration: none;">💬 WhatsApp</a>` : ''}
            ${st !== 'FINALIZADO' ? `<button type="button" class="btn btn-sm btn-success" onclick="abrirModalBaixaEntregaMobile(${idx})" style="padding: 4px 8px; font-size: 0.75rem;">✍️ Entregar</button>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = html;
  if (resumo) {
    resumo.textContent = `${mobileItensAtuais.length} Entregas (${finalizadas} Finalizadas) | Total: R$ ${totalFrete.toFixed(2)}`;
  }
}

async function marcarTodosEmTransporteMobile() {
  if (!mobileItensAtuais.length) return;
  if (!confirm(`Deseja alterar o status de todas as entregas pendentes para "EM TRANSPORTE"?`)) return;

  let count = 0;
  for (const it of mobileItensAtuais) {
    if (it.status_entrega !== "FINALIZADO") {
      try {
        await fetch("/.netlify/functions/turso-db?action=update_status_entrega", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prepostagem_id: it.prepostagem_id,
            codigo_objeto: it.codigo_objeto,
            status_entrega: "EM_TRANSPORTE"
          })
        });
        it.status_entrega = "EM_TRANSPORTE";
        count++;
      } catch (e) {}
    }
  }
  alert(`🚚 ${count} entregas marcadas como EM TRANSPORTE!`);
  renderEntregasMobile();
}

function biparEntregaMobile() {
  const inp = document.getElementById("mobileInputBipagem");
  if (!inp || !inp.value.trim()) return;
  const termo = inp.value.trim().toUpperCase();

  const idx = mobileItensAtuais.findIndex(it => 
    (it.codigo_objeto && it.codigo_objeto.toUpperCase() === termo) ||
    (it.pedido && String(it.pedido).toUpperCase() === termo) ||
    (it.numero_nf && String(it.numero_nf).toUpperCase() === termo)
  );

  if (idx !== -1) {
    abrirModalBaixaEntregaMobile(idx);
    inp.value = "";
  } else {
    alert(`Objeto ou pedido "${termo}" não encontrado neste romaneio.`);
  }
}

let canvasAssinaturaCtx = null;
let desenhandoAssinatura = false;

function initCanvasAssinatura() {
  const canvas = document.getElementById("canvasAssinatura");
  if (!canvas) return;
  canvasAssinaturaCtx = canvas.getContext("2d");
  canvasAssinaturaCtx.lineWidth = 2.5;
  canvasAssinaturaCtx.lineCap = "round";
  canvasAssinaturaCtx.strokeStyle = "#000";

  const getPos = (e) => {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: (clientX - rect.left) * (canvas.width / rect.width),
      y: (clientY - rect.top) * (canvas.height / rect.height)
    };
  };

  const startDraw = (e) => {
    e.preventDefault();
    desenhandoAssinatura = true;
    const pos = getPos(e);
    canvasAssinaturaCtx.beginPath();
    canvasAssinaturaCtx.moveTo(pos.x, pos.y);
  };

  const draw = (e) => {
    if (!desenhandoAssinatura) return;
    e.preventDefault();
    const pos = getPos(e);
    canvasAssinaturaCtx.lineTo(pos.x, pos.y);
    canvasAssinaturaCtx.stroke();
  };

  const stopDraw = () => {
    desenhandoAssinatura = false;
  };

  canvas.onmousedown = startDraw;
  canvas.onmousemove = draw;
  canvas.onmouseup = stopDraw;
  canvas.ontouchstart = startDraw;
  canvas.ontouchmove = draw;
  canvas.ontouchend = stopDraw;
}

function limparCanvasAssinatura() {
  const canvas = document.getElementById("canvasAssinatura");
  if (canvas && canvasAssinaturaCtx) {
    canvasAssinaturaCtx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

function abrirModalBaixaEntregaMobile(idx) {
  const item = mobileItensAtuais[idx];
  if (!item) return;

  const modal = document.getElementById("modalBaixaEntregaMobile");
  if (!modal) return;

  document.getElementById("baixaItemId").value = idx;
  document.getElementById("baixaListaId").value = mobileListaIdAtual;
  document.getElementById("modalBaixaTitulo").textContent = `✍️ Baixa: ${item.codigo_objeto || item.destinatario}`;
  document.getElementById("baixaRecebedorNome").value = item.destinatario || "";
  document.getElementById("baixaRecebedorDoc").value = "";

  limparCanvasAssinatura();
  initCanvasAssinatura();
  modal.style.display = "flex";
}

function fecharModalBaixaEntregaMobile() {
  const modal = document.getElementById("modalBaixaEntregaMobile");
  if (modal) modal.style.display = "none";
}

async function salvarFinalizacaoEntregaMobile() {
  const idx = parseInt(document.getElementById("baixaItemId")?.value, 10);
  const item = mobileItensAtuais[idx];
  if (!item) return;

  const nome = document.getElementById("baixaRecebedorNome")?.value.trim();
  const doc = document.getElementById("baixaRecebedorDoc")?.value.trim();
  const canvas = document.getElementById("canvasAssinatura");
  const assinaturaB64 = canvas ? canvas.toDataURL("image/png") : "";

  if (!nome) {
    alert("Informe o nome de quem recebeu a entrega.");
    return;
  }

  try {
    const res = await fetch("/.netlify/functions/turso-db?action=update_status_entrega", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prepostagem_id: item.prepostagem_id,
        codigo_objeto: item.codigo_objeto,
        status_entrega: "FINALIZADO",
        recebedor_nome: nome,
        recebedor_doc: doc,
        assinatura_base64: assinaturaB64
      })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao salvar baixa.");

    item.status_entrega = "FINALIZADO";
    item.recebedor_nome = nome;
    fecharModalBaixaEntregaMobile();
    renderEntregasMobile();
    renderEntregasAba10Cards();
    alert(`✅ Entrega de ${item.destinatario} finalizada com sucesso!`);
  } catch (err) {
    alert(`Falha ao finalizar entrega: ${err.message}`);
  }
}


// ==========================================================================
// ABA 6: GERAR ETIQUETA MANUAL
// ==========================================================================

function toggleDocFields() {
  const tipo = document.getElementById("manTipoDoc")?.value || "NF";
  const grpChave = document.getElementById("groupChaveNF");
  const grpNum = document.getElementById("groupNumNF");
  if (grpChave) grpChave.style.display = tipo === "NF" ? "flex" : "none";
  if (grpNum) grpNum.style.display = tipo === "NF" ? "flex" : "none";
}


// CONTROLE DE SUB-ABAS DA ABA 6 (GERAÇÃO MANUAL & ENTRADAS AVULSAS)
function alternarSubabaManual(modo) {
  const btnGeral = document.getElementById("subtabBtnManualGeral");
  const btnAvulsa = document.getElementById("subtabBtnManualAvulsa");
  const contGeral = document.getElementById("subabaContainerManualGeral");
  const contAvulsa = document.getElementById("subabaContainerManualAvulsa");

  if (modo === "AVULSA") {
    if (btnGeral) {
      btnGeral.style.background = "rgba(14, 165, 233, 0.15)";
      btnGeral.style.color = "#38bdf8";
      btnGeral.style.border = "1px solid #0ea5e9";
    }
    if (btnAvulsa) {
      btnAvulsa.style.background = "#0ea5e9";
      btnAvulsa.style.color = "#fff";
      btnAvulsa.style.border = "none";
    }
    if (contGeral) contGeral.style.display = "none";
    if (contAvulsa) contAvulsa.style.display = "block";
    if (typeof carregarLocaisAvulsosSalvos === "function") carregarLocaisAvulsosSalvos();
  } else {
    if (btnGeral) {
      btnGeral.style.background = "#0284c7";
      btnGeral.style.color = "#fff";
      btnGeral.style.border = "none";
    }
    if (btnAvulsa) {
      btnAvulsa.style.background = "rgba(14, 165, 233, 0.15)";
      btnAvulsa.style.color = "#38bdf8";
      btnAvulsa.style.border = "1px solid #0ea5e9";
    }
    if (contGeral) contGeral.style.display = "block";
    if (contAvulsa) contAvulsa.style.display = "none";
  }
}
window.alternarSubabaManual = alternarSubabaManual;

async function salvarNovaEntradaAvulsaSubaba() {
  const desc = document.getElementById("abaAvulsaDescricao")?.value.trim();
  const dest = document.getElementById("abaAvulsaDestinatario")?.value.trim();
  const end = document.getElementById("abaAvulsaEndereco")?.value.trim();
  const bairro = document.getElementById("abaAvulsaBairro")?.value.trim();
  const cidade = document.getElementById("abaAvulsaCidade")?.value.trim() || "Fortaleza";
  const cep = document.getElementById("abaAvulsaCep")?.value.trim();
  const frete = parseFloat(document.getElementById("abaAvulsaValorFrete")?.value) || 11.50;
  const peso = parseFloat(document.getElementById("abaAvulsaPeso")?.value) || 1.0;
  const obs = document.getElementById("abaAvulsaObs")?.value.trim();

  if (!desc || !dest) {
    alert("Preencha a descrição do serviço e o destinatário/local.");
    return;
  }

  try {
    const res = await fetch("/.netlify/functions/turso-db?action=save_prepostagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pedido: "AVULSO",
        numero_nf: "SEM_NF",
        destinatario: dest,
        logradouro: end || "Coleta / Entrega Externa",
        numero: "S/N",
        bairro: bairro || "Fortaleza",
        cidade: cidade,
        uf: "CE",
        cep: cep || "60000000",
        servico: "ENTREGA_PROPRIA",
        obs_entrega: obs,
        valor_frete: frete,
        tipo_item: "AVULSO",
        descricao_avulsa: desc,
        origem_postagem: "SOUZA_LOCAL",
        status: "PRONTO",
        status_impressao: "PRONTO",
        status_entrega: "EM_COLETA"
      })
    });
    const data = await safeFetchJson(res);
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao salvar entrada avulsa");

    alert(`✅ Entrada Avulsa gerada com sucesso!\nCódigo de Rastreio: ${data.codigo_objeto}\n\nDisponível na Aba 2 (Etiquetas para Impressão) para imprimir o rótulo e na Aba 5 para o fechamento do romaneio.`);
    
    // Limpar campos
    document.getElementById("abaAvulsaDescricao").value = "";
    document.getElementById("abaAvulsaDestinatario").value = "";
    document.getElementById("abaAvulsaEndereco").value = "";
    document.getElementById("abaAvulsaBairro").value = "";
    document.getElementById("abaAvulsaCep").value = "";
    document.getElementById("abaAvulsaObs").value = "";

    await carregarEtiquetasDoTurso();
    await carregarObjetosElegiveisPlp();
  } catch (err) {
    alert(`Erro ao cadastrar entrada avulsa: ${err.message}`);
  }
}
window.salvarNovaEntradaAvulsaSubaba = salvarNovaEntradaAvulsaSubaba;

function initManualTab() {
  const btn = document.getElementById("btnGerarManual");
  if (btn) {
    btn.addEventListener("click", async () => {
      const nome = document.getElementById("manNome")?.value.trim() || "";
      const cpf = document.getElementById("manCpfCnpj")?.value.trim() || "";
      const cep = document.getElementById("manCep")?.value.trim() || "";
      const logradouro = document.getElementById("manLogradouro")?.value.trim() || "";
      const numero = document.getElementById("manNumero")?.value.trim() || "S/N";
      const complemento = document.getElementById("manComplemento")?.value.trim() || "";
      const bairro = document.getElementById("manBairro")?.value.trim() || "";
      const cidade = document.getElementById("manCidade")?.value.trim() || "";
      const uf = document.getElementById("manUf")?.value.trim().toUpperCase() || "";
      const servico = document.getElementById("manServico")?.value || "PAC";
      const chaveNfe = document.getElementById("manChaveNFe")?.value.trim() || "";
      const numNf = document.getElementById("manNumNF")?.value.trim() || "";

      if (!nome || !cep || !logradouro || !cidade || !uf) {
        alert("Preencha todos os campos obrigatórios (*) do destinatário.");
        return;
      }

      btn.disabled = true;
      const orig = btn.textContent;
      btn.textContent = "⏳ Gerando Etiqueta Manual...";

      try {
        const valFrete = parseFloat(document.getElementById("manValorFrete")?.value) || 11.50;
        const obsManual = document.getElementById("manObsEntrega")?.value.trim() || "";
        const isSouzaManual = servico === "ENTREGA_PROPRIA" || servico.includes("SOUZA");

        const pedManual = {
          numero_pedido: "MANUAL",
          numero_nf: numNf,
          chave_nfe: chaveNfe,
          forma_envio: servico,
          servico: servico,
          transportadora_normalizada: isSouzaManual ? "SOUZA" : "CORREIOS",
          valor_frete: valFrete,
          obs_entrega: obsManual,
          destinatario: {
            nome,
            cpfCnpj: cpf,
            endereco: { cep, logradouro, numero, complemento, bairro, cidade, uf }
          }
        };
        const res = await emitirPedidoObjeto(pedManual, 1);
        alert(`✅ Etiqueta manual gerada com sucesso!\nObjeto: ${res[0]?.codigoObjeto || ''}\nDisponível na Aba 2 (Etiquetas para Impressão).`);
        await carregarEtiquetasDoTurso();
      } catch (err) {
        alert(`❌ Erro ao gerar etiqueta manual: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = orig;
      }
    });
  }
}

// ==========================================================================
// ABA 7: IMPORTAR XML NF-E EM LOTE
// ==========================================================================

let xmlItemsCarregados = [];

function initXmlImport() {
  const input = document.getElementById("inputXmlFile");
  if (!input) return;

  input.addEventListener("change", async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    xmlItemsCarregados = [];
    for (const file of files) {
      try {
        const text = await file.text();
        const parser = new DOMParser();
        const xml = parser.parseFromString(text, "text/xml");

        const chave = xml.querySelector("chNFe")?.textContent || "";
        const nNF = xml.querySelector("ide > nNF")?.textContent || "";
        const vNF = xml.querySelector("ICMSTot > vNF")?.textContent || "0.00";
        const dest = xml.querySelector("dest");
        const ender = dest?.querySelector("enderDest");

        const nome = dest?.querySelector("xNome")?.textContent || "";
        const cpfCnpj = dest?.querySelector("CPF")?.textContent || dest?.querySelector("CNPJ")?.textContent || "";
        const logradouro = ender?.querySelector("xLgr")?.textContent || "";
        const numero = ender?.querySelector("nro")?.textContent || "S/N";
        const complemento = ender?.querySelector("xCpl")?.textContent || "";
        const bairro = ender?.querySelector("xBairro")?.textContent || "";
        const cidade = ender?.querySelector("xMun")?.textContent || "";
        const uf = ender?.querySelector("UF")?.textContent || "";
        const cep = ender?.querySelector("CEP")?.textContent || "";

        xmlItemsCarregados.push({
          arquivo: file.name,
          nNF,
          chave,
          nome,
          cpfCnpj,
          valor: vNF,
          endereco: { logradouro, numero, complemento, bairro, cidade, uf, cep },
          valido: Boolean(chave && nome && cep)
        });
      } catch (err) {
        xmlItemsCarregados.push({
          arquivo: file.name,
          nNF: "-",
          chave: "",
          nome: "Erro ao ler XML",
          valor: "0.00",
          valido: false
        });
      }
    }

    renderXmlPreview();
  });
}

function renderXmlPreview() {
  const area = document.getElementById("xmlPreviewArea");
  const tbody = document.getElementById("tableBodyXmlItems");
  if (!area || !tbody) return;

  area.style.display = xmlItemsCarregados.length > 0 ? "block" : "none";
  document.getElementById("xmlTotalCount").textContent = xmlItemsCarregados.length;
  document.getElementById("xmlValidCount").textContent = xmlItemsCarregados.filter(x => x.valido).length;
  document.getElementById("xmlErrorCount").textContent = xmlItemsCarregados.filter(x => !x.valido).length;

  tbody.innerHTML = xmlItemsCarregados.map((item, idx) => `
    <tr>
      <td style="text-align:center;">
        <input type="checkbox" class="chk-xml-item" data-idx="${idx}" ${item.valido ? "checked" : "disabled"}>
      </td>
      <td><strong>NF ${item.nNF}</strong><br><small>${item.arquivo}</small></td>
      <td><small>${item.chave || '-'}</small></td>
      <td>${item.nome}</td>
      <td>R$ ${Number(item.valor || 0).toFixed(2)}</td>
      <td><span class="badge ${item.valido ? 'badge-success' : 'badge-danger'}">${item.valido ? 'VÁLIDO' : 'INVÁLIDO'}</span></td>
      <td>${item.endereco ? `${item.endereco.cidade}/${item.endereco.uf} - CEP ${item.endereco.cep}` : '-'}</td>
    </tr>
  `).join("");

  const btnEmitir = document.getElementById("btnEmitirXmlLote");
  if (btnEmitir) btnEmitir.disabled = xmlItemsCarregados.filter(x => x.valido).length === 0;
}

function toggleSelectAllXml(chk) {
  document.querySelectorAll(".chk-xml-item:not(:disabled)").forEach(c => {
    c.checked = chk.checked;
  });
}

function limparXmlsCarregados() {
  xmlItemsCarregados = [];
  const input = document.getElementById("inputXmlFile");
  if (input) input.value = "";
  renderXmlPreview();
}

async function gerarPrepostagensXmlLote() {
  const chks = Array.from(document.querySelectorAll(".chk-xml-item:checked"));
  if (chks.length === 0) return;

  const servicoPadrao = document.getElementById("xmlServicoPadrao")?.value || "PAC";
  let sucessos = 0;

  for (const chk of chks) {
    const item = xmlItemsCarregados[parseInt(chk.dataset.idx, 10)];
    if (!item || !item.valido) continue;
    try {
      await emitirPedidoObjeto({
        numero_pedido: `XML_${item.nNF}`,
        numero_nf: item.nNF,
        chave_nfe: item.chave,
        forma_envio: servicoPadrao,
        servico: servicoPadrao,
        destinatario: {
          nome: item.nome,
          cpfCnpj: item.cpfCnpj,
          endereco: item.endereco
        }
      }, 1);
      sucessos++;
    } catch (e) {
      console.error("Erro XML lote:", e);
    }
  }

  alert(`✅ ${sucessos} pré-postagem(ns) gerada(s) a partir dos XMLs!`);
  limparXmlsCarregados();
  await carregarEtiquetasDoTurso();
}

// ==========================================================================
// ABA 8: GERENCIAR RANGES IMPRESSO MÓDICO
// ==========================================================================

function initRangesModico() {
  carregarRangesModico();
}

async function carregarRangesModico() {
  const tbody = document.getElementById("tableBodyRangesModico");
  if (!tbody) return;

  try {
    const res = await fetch("/.netlify/functions/turso-db?action=list_ranges");
    const data = await safeFetchJson(res);
    const ranges = data.ranges || [];

    if (ranges.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Nenhum range cadastrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = ranges.map(r => `
      <tr>
        <td>#${r.id}</td>
        <td><strong>${r.prefixo || 'YD'}</strong></td>
        <td>${r.numero_inicial} até ${r.numero_final}</td>
        <td><strong style="color:#38bdf8;">${r.numero_atual}</strong></td>
        <td><span class="badge ${r.ativo ? 'badge-success' : 'badge-secondary'}">${r.ativo ? 'ATIVO' : 'ESGOTADO'}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Erro ao carregar ranges módico:", err);
  }
}

async function salvarNovoRangeModico(event) {
  if (event) event.preventDefault();
  const sigla = document.getElementById("rangeSigla")?.value.trim().toUpperCase() || "YD";
  const inicio = document.getElementById("rangeInicio")?.value.trim() || "";
  const fim = document.getElementById("rangeFim")?.value.trim() || "";

  if (!sigla || !inicio || !fim) return;

  try {
    const res = await fetch("/.netlify/functions/turso-db?action=save_range_modico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sigla, inicio, fim })
    });
    const data = await safeFetchJson(res);
    if (res.ok && data.success) {
      alert("✅ Novo Range Impresso Módico salvo com sucesso!");
      document.getElementById("formNovoRangeModico")?.reset();
      await carregarRangesModico();
    } else {
      alert("❌ Erro ao salvar range: " + (data.error || "Falha desconhecida"));
    }
  } catch (err) {
    alert("❌ Erro: " + err.message);
  }
}


// =======================================================================
// ABA 10: APP MOTORISTA DEDICADO — ROBERTO SOUZA
// =======================================================================
let aba10RomaneiosSouza = [];
let aba10ItensAtuais = [];
let aba10ListaIdAtual = null;

async function carregarEntregasAba10Motorista() {
  const sel = document.getElementById("aba10SelectRomaneio");
  const container = document.getElementById("aba10CardsContainer");
  if (container) {
    container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 30px;">⏳ Buscando romaneios do Souza...</div>`;
  }

  try {
    const res = await fetch("/.netlify/functions/lista-postagem?action=list_listas&transportadora=SOUZA&status=GERADA");
    const data = await safeFetchJson(res);
    aba10RomaneiosSouza = data.listas || [];

    if (sel) {
      if (aba10RomaneiosSouza.length === 0) {
        sel.innerHTML = `<option value="">Nenhum romaneio Souza gerado</option>`;
        if (container) container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 40px; background: #0f172a; border-radius: 10px;">Nenhum romaneio do Roberto Souza gerado até o momento.</div>`;
        atualizarKpisAba10([]);
        return;
      }

      sel.innerHTML = aba10RomaneiosSouza.map((l, i) => `
        <option value="${l.id}" ${i === 0 ? 'selected' : ''}>
          Romaneio #${l.numero_lista} - ${l.data_geracao ? l.data_geracao.substring(0,10) : ''} (${l.quantidade_objetos} entregas - ${l.status})
        </option>
      `).join("");
      
      aba10ListaIdAtual = aba10RomaneiosSouza[0].id;
      await carregarItensRomaneioAba10(aba10ListaIdAtual);
    }
  } catch (err) {
    console.error("Erro ao carregar Aba 10:", err);
    if (container) container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">Erro: ${err.message}</div>`;
  }
}
window.carregarEntregasAba10Motorista = carregarEntregasAba10Motorista;

async function selecionarRomaneioAba10() {
  const sel = document.getElementById("aba10SelectRomaneio");
  if (!sel || !sel.value) return;
  aba10ListaIdAtual = parseInt(sel.value, 10);
  await carregarItensRomaneioAba10(aba10ListaIdAtual);
}
window.selecionarRomaneioAba10 = selecionarRomaneioAba10;

async function carregarItensRomaneioAba10(listaId) {
  const container = document.getElementById("aba10CardsContainer");
  if (container) {
    container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 30px;">⏳ Carregando entregas do romaneio #${listaId}...</div>`;
  }

  try {
    const res = await fetch(`/.netlify/functions/lista-postagem?action=get_lista&lista_id=${listaId}`);
    const data = await safeFetchJson(res);
    aba10ItensAtuais = data.itens || [];
    mobileItensAtuais = aba10ItensAtuais;
    mobileListaIdAtual = listaId;

    atualizarKpisAba10(aba10ItensAtuais);
    renderEntregasAba10Cards();
  } catch (err) {
    if (container) container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 20px;">Erro ao carregar itens: ${err.message}</div>`;
  }
}

function atualizarKpisAba10(itens) {
  let total = itens.length;
  let emTransp = 0;
  let fin = 0;
  let totalFrete = 0.0;

  itens.forEach(it => {
    const st = (it.status_entrega || "EM_COLETA").toUpperCase();
    if (st === "FINALIZADO") fin++;
    else if (st === "EM_TRANSPORTE") emTransp++;
    totalFrete += Number(it.valor_frete || 11.50);
  });

  const elTot = document.getElementById("aba10KpiTotal");
  const elTr = document.getElementById("aba10KpiTransporte");
  const elFin = document.getElementById("aba10KpiFinalizadas");
  const elFr = document.getElementById("aba10KpiFrete");

  if (elTot) elTot.textContent = total;
  if (elTr) elTr.textContent = emTransp;
  if (elFin) elFin.textContent = fin;
  if (elFr) elFr.textContent = `R$ ${totalFrete.toFixed(2)}`;
}

function renderEntregasAba10Cards(filtrados = null) {
  const container = document.getElementById("aba10CardsContainer");
  if (!container) return;

  const itens = filtrados || aba10ItensAtuais;
  if (itens.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 40px; background: #0f172a; border-radius: 10px;">Nenhuma entrega encontrada para este romaneio ou filtro.</div>`;
    return;
  }

  container.innerHTML = itens.map((it, idx) => {
    const st = (it.status_entrega || "EM_COLETA").toUpperCase();
    const isFin = st === "FINALIZADO";
    const isTransp = st === "EM_TRANSPORTE";

    const badgeStatus = isFin
      ? `<span class="badge badge-success" style="font-size: 0.8rem; padding: 4px 10px;">✅ ENTREGUE</span>`
      : (isTransp 
          ? `<span class="badge" style="background: rgba(245,158,11,0.25); color: #fbbf24; border: 1px solid #f59e0b; font-size: 0.8rem; padding: 4px 10px;">🚚 EM TRANSPORTE</span>`
          : `<span class="badge badge-secondary" style="font-size: 0.8rem; padding: 4px 10px;">📦 EM COLETA</span>`);

    const endFormatado = `${it.logradouro || ''}, ${it.numero || 'S/N'}${it.complemento ? ' ' + it.complemento : ''} ${it.bairro ? '- ' + it.bairro : ''} - ${it.cidade || 'Fortaleza'}/${it.uf || 'CE'}`;
    const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(endFormatado + ' ' + (it.cep || ''))}`;
    const fone = it.telefone_contato || it.telefone || "";
    const wppUrl = fone ? `https://wa.me/55${fone.replace(/\D/g, '')}` : null;

    return `
      <div style="background: #1e293b; border: 1.5px solid ${isFin ? '#10b981' : (isTransp ? '#f59e0b' : '#334155')}; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: flex; flex-direction: column; gap: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div>
            <span style="font-size: 1.05rem; font-weight: 800; color: #38bdf8;">${it.codigo_objeto || '-'}</span>
            <span style="font-size: 0.82rem; color: #94a3b8; margin-left: 8px; font-weight: 600;">(Pedido #${it.pedido || '-'}${it.numero_nf ? ' / NF ' + it.numero_nf : ''})</span>
          </div>
          <div>${badgeStatus}</div>
        </div>

        <div>
          <div style="font-size: 1rem; font-weight: 800; color: #f8fafc;">${it.destinatario || '-'}</div>
          <div style="font-size: 0.86rem; color: #cbd5e1; margin-top: 3px; display: flex; align-items: center; gap: 6px;">
            <span>📍</span> <span>${endFormatado} (CEP: ${it.cep || '-'})</span>
          </div>
          ${it.observacoes_entrega ? `
            <div style="background: rgba(245,158,11,0.15); border-left: 4px solid #f59e0b; padding: 6px 10px; border-radius: 4px; margin-top: 6px; font-size: 0.82rem; color: #fde68a;">
              <strong>⚠️ Instrução / Observação:</strong> ${it.observacoes_entrega}
            </div>
          ` : ''}
          ${it.recebedor_nome ? `
            <div style="background: rgba(16,185,129,0.15); border-left: 4px solid #10b981; padding: 6px 10px; border-radius: 4px; margin-top: 6px; font-size: 0.82rem; color: #6ee7b7;">
              <strong>Assinado por:</strong> ${it.recebedor_nome} ${it.recebedor_doc ? '(' + it.recebedor_doc + ')' : ''} em ${it.data_entrega || 'Hoje'}
            </div>
          ` : ''}
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #334155; padding-top: 10px; flex-wrap: wrap; gap: 8px;">
          <div style="font-size: 0.95rem; color: #10b981; font-weight: 800;">
            Frete a Receber: R$ ${Number(it.valor_frete || 11.50).toFixed(2)}
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <a href="${mapsUrl}" target="_blank" class="btn btn-sm" style="background: #0284c7; color: #fff; text-decoration: none; font-weight: 700; padding: 6px 12px; border-radius: 6px;">
              🗺️ Rotas Maps
            </a>
            ${wppUrl ? `
              <a href="${wppUrl}" target="_blank" class="btn btn-sm" style="background: #16a34a; color: #fff; text-decoration: none; font-weight: 700; padding: 6px 12px; border-radius: 6px;">
                💬 WhatsApp
              </a>
            ` : ''}
            ${!isFin ? `
              <button type="button" class="btn btn-sm btn-success" onclick="abrirModalBaixaEntregaAba10(${idx})" style="background: #10b981; font-weight: 800; padding: 6px 14px; border-radius: 6px;">
                ✍️ Entregar & Baixa
              </button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function abrirModalBaixaEntregaAba10(idx) {
  mobileItensAtuais = aba10ItensAtuais;
  mobileListaIdAtual = aba10ListaIdAtual;
  abrirModalBaixaEntregaMobile(idx);
}
window.abrirModalBaixaEntregaAba10 = abrirModalBaixaEntregaAba10;

function biparEntregaAba10() {
  const inp = document.getElementById("aba10InputBipagem");
  if (!inp || !inp.value.trim()) {
    renderEntregasAba10Cards();
    return;
  }
  const termo = inp.value.trim().toUpperCase();

  // Se achar exato, abre modal de entrega
  const idx = aba10ItensAtuais.findIndex(it => 
    (it.codigo_objeto && it.codigo_objeto.toUpperCase() === termo) ||
    (it.pedido && String(it.pedido).toUpperCase() === termo) ||
    (it.numero_nf && String(it.numero_nf).toUpperCase() === termo)
  );

  if (idx !== -1) {
    abrirModalBaixaEntregaAba10(idx);
    inp.value = "";
  } else {
    // Filtra lista de cards por substring
    const filtrados = aba10ItensAtuais.filter(it => 
      (it.codigo_objeto && it.codigo_objeto.toUpperCase().includes(termo)) ||
      (it.destinatario && it.destinatario.toUpperCase().includes(termo)) ||
      (it.pedido && String(it.pedido).toUpperCase().includes(termo)) ||
      (it.logradouro && it.logradouro.toUpperCase().includes(termo)) ||
      (it.bairro && it.bairro.toUpperCase().includes(termo))
    );
    renderEntregasAba10Cards(filtrados);
  }
}
window.biparEntregaAba10 = biparEntregaAba10;

async function marcarTodosEmTransporteAba10() {
  if (!aba10ItensAtuais.length) return;
  if (!confirm(`Deseja marcar todas as entregas pendentes deste romaneio como "EM TRANSPORTE"?`)) return;

  let count = 0;
  for (const it of aba10ItensAtuais) {
    if (it.status_entrega !== "FINALIZADO") {
      try {
        await fetch("/.netlify/functions/turso-db?action=update_status_entrega", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prepostagem_id: it.prepostagem_id,
            codigo_objeto: it.codigo_objeto,
            status_entrega: "EM_TRANSPORTE"
          })
        });
        it.status_entrega = "EM_TRANSPORTE";
        count++;
      } catch (e) {}
    }
  }
  alert(`🚚 ${count} entregas atualizadas para EM TRANSPORTE!`);
  atualizarKpisAba10(aba10ItensAtuais);
  renderEntregasAba10Cards();
}
window.marcarTodosEmTransporteAba10 = marcarTodosEmTransporteAba10;
