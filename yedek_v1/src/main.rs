mod udf_manager;

use axum::{
    body::Body,
    extract::Multipart,
    http::{header, Response, StatusCode},
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;

#[derive(Serialize)]
struct UdfResponse {
    success: bool,
    content: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct SaveRequest {
    xml_content: String,
}

// Dosya Seçiciden gelen UDF'yi çözen API
async fn upload_udf_handler(mut multipart: Multipart) -> Json<UdfResponse> {
    while let Some(field) = multipart.next_field().await.unwrap_or(None) {
        if field.name() == Some("file") {
            let data = field.bytes().await.unwrap_or_default();
            match udf_manager::extract_content_xml_from_bytes(&data) {
                Ok(xml) => return Json(UdfResponse { success: true, content: Some(xml), error: None }),
                Err(e) => return Json(UdfResponse { success: false, content: None, error: Some(e.to_string()) }),
            }
        }
    }
    Json(UdfResponse { success: false, content: None, error: Some("Dosya ulaşmadı.".to_string()) })
}

// YENİ: JS'ten gelen güncel XML'i alıp .udf dosyası olarak indirmeyi tetikleyen API
async fn download_udf_handler(Json(payload): Json<SaveRequest>) -> Result<Response<Body>, (StatusCode, String)> {
    match udf_manager::package_udf_to_bytes(&payload.xml_content) {
        Ok(zip_bytes) => {
            let response = Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, "application/octet-stream")
                .header(header::CONTENT_DISPOSITION, "attachment; filename=\"duzenlenmis_dilekce.udf\"")
                .body(Body::from(zip_bytes))
                .unwrap();
            Ok(response)
        }
        Err(e) => Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
    }
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/api/upload_udf", post(upload_udf_handler))
        .route("/api/download_udf", post(download_udf_handler)) // Rota eklendi
        .layer(CorsLayer::permissive());

    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("UYAP Çekirdek Sunucusu çalışıyor: http://{}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
