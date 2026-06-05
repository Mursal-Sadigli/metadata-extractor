import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

export const exportToPDF = async (elementId, filename) => {
  const element = document.getElementById(elementId);
  if (!element) {
    console.error("PDF Export error: Element not found");
    return;
  }

  try {
    // PDF generation requires the element to be visible and fully rendered
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#0f172a' // Dark background matching the app
    });

    const imgData = canvas.toDataURL('image/png');
    
    // A4 dimensions: 210 x 297 mm
    const pdf = new jsPDF('p', 'mm', 'a4');
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

    // Add header
    pdf.setFillColor(15, 23, 42);
    pdf.rect(0, 0, pdfWidth, 20, 'F');
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(16);
    pdf.text("KƏŞFİYYAT HESABATI (OSINT DOSSIER)", 14, 13);
    
    pdf.setFontSize(10);
    pdf.setTextColor(150, 150, 150);
    const dateStr = new Date().toLocaleString('az-AZ');
    pdf.text(`Tarix: ${dateStr}`, pdfWidth - 50, 13);

    // Add main content
    pdf.addImage(imgData, 'PNG', 0, 25, pdfWidth, pdfHeight);

    pdf.save(`Intelligence_Report_${filename.split('.')[0] || 'file'}.pdf`);
  } catch (err) {
    console.error("Failed to generate PDF", err);
    alert("PDF yaradılarkən xəta baş verdi.");
  }
};
