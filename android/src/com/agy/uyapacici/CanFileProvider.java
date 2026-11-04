package com.agy.uyapacici;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Environment;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.Locale;

/**
 * CanEditor Güvenli Dosya Sağlayıcısı
 * Harici uygulamalarla (WhatsApp, Gmail, Telegram, Word, Adobe Acrobat)
 * UDF, PDF, DOCX, ODT ve TIFF belgelerinin sorunsuz paylaşılmasını sağlar.
 */
public class CanFileProvider extends ContentProvider {
    public static final String AUTHORITY = "com.agy.uyapacici.fileprovider";

    @Override
    public boolean onCreate() {
        return true;
    }

    private File resolveFile(Uri uri) {
        if (uri == null) return null;
        String path = uri.getPath();
        if (path == null) return null;

        File file = new File(path);
        if (file.exists()) return file;

        String fileName = file.getName();
        if (getContext() != null) {
            if (getContext().getExternalCacheDir() != null) {
                File alt = new File(getContext().getExternalCacheDir(), fileName);
                if (alt.exists()) return alt;
            }
            if (getContext().getCacheDir() != null) {
                File alt = new File(getContext().getCacheDir(), fileName);
                if (alt.exists()) return alt;
            }
            try {
                File pub = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "CanEditor/" + fileName);
                if (pub.exists()) return pub;
                File pubUyap = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "UYAP_Belgelerim/" + fileName);
                if (pubUyap.exists()) return pubUyap;
            } catch (Exception ignored) {}
        }
        return file;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        File file = resolveFile(uri);
        if (file == null || !file.exists()) {
            throw new FileNotFoundException("Paylaşılan dosya bulunamadı: " + (uri != null ? uri.getPath() : "null"));
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        File file = resolveFile(uri);
        String fileName = (file != null) ? file.getName() : "belge";
        long fileSize = (file != null && file.exists()) ? file.length() : 0L;

        if (projection == null) {
            projection = new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
        }
        MatrixCursor cursor = new MatrixCursor(projection, 1);
        MatrixCursor.RowBuilder row = cursor.newRow();
        for (String col : projection) {
            if (OpenableColumns.DISPLAY_NAME.equals(col)) {
                row.add(fileName);
            } else if (OpenableColumns.SIZE.equals(col)) {
                row.add(fileSize);
            } else {
                row.add(null);
            }
        }
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        if (uri == null) return "application/octet-stream";
        String name = uri.getLastPathSegment();
        if (name != null) {
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            if (lower.endsWith(".pdf")) return "application/pdf";
            if (lower.endsWith(".udf")) return "application/octet-stream";
            if (lower.endsWith(".odt")) return "application/vnd.oasis.opendocument.text";
            if (lower.endsWith(".tiff") || lower.endsWith(".tif")) return "image/tiff";
            if (lower.endsWith(".txt")) return "text/plain";
            if (lower.endsWith(".png")) return "image/png";
            if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        }
        return "application/octet-stream";
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) { return 0; }
    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) { return 0; }
}
