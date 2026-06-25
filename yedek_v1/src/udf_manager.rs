use std::io::{Cursor, Read, Write};
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

// 1. UDF BAYTLARINI HAFIZADA AÇAN MOTOR
pub fn extract_content_xml_from_bytes(data: &[u8]) -> Result<String, Box<dyn std::error::Error>> {
    let reader = Cursor::new(data);
    let mut archive = ZipArchive::new(reader)?;

    let mut content_file = archive.by_name("content.xml")?;
    let mut xml_content = String::new();
    content_file.read_to_string(&mut xml_content)?;

    Ok(xml_content)
}

// 2. YENİ: UDF'Yİ HAFIZADA PAKETLEYEN MOTOR (Disk yerine RAM kullanır)
// Dosya izni dertlerini çözer ve doğrudan tarayıcıya indirme linki verir
pub fn package_udf_to_bytes(xml_content: &str) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut buffer = Cursor::new(Vec::new());
    
    {
        let mut zip = ZipWriter::new(&mut buffer);
        let options = SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated)
            .unix_permissions(0o755);

        zip.start_file("content.xml", options)?;
        zip.write_all(xml_content.as_bytes())?;
        zip.finish()?;
    }
    
    Ok(buffer.into_inner())
}
