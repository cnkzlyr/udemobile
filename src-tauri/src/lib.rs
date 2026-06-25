use std::io::{Cursor, Read, Write};
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

// DEĞİŞİM: Artık REST API değil, Tauri Command kullanıyoruz
#[tauri::command]
fn extract_udf(data: Vec<u8>) -> Result<String, String> {
    let reader = Cursor::new(data);
    let mut archive = ZipArchive::new(reader).map_err(|e| e.to_string())?;
    let mut content_file = archive.by_name("content.xml").map_err(|e| e.to_string())?;
    let mut xml_content = String::new();
    content_file.read_to_string(&mut xml_content).map_err(|e| e.to_string())?;
    Ok(xml_content)
}

// DEĞİŞİM: Sıkıştırılan dosyayı RAM'den direkt uygulamaya fırlatıyoruz
#[tauri::command]
fn package_udf(xml_content: String) -> Result<Vec<u8>, String> {
    let mut buffer = Cursor::new(Vec::new());
    {
        let mut zip = ZipWriter::new(&mut buffer);
        let options = SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated)
            .unix_permissions(0o755);
        zip.start_file("content.xml", options).map_err(|e| e.to_string())?;
        zip.write_all(xml_content.as_bytes()).map_err(|e| e.to_string())?;
        zip.finish().map_err(|e| e.to_string())?;
    }
    Ok(buffer.into_inner())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![extract_udf, package_udf])
        .run(tauri::generate_context!())
        .expect("Tauri motoru başlatılamadı");
}
