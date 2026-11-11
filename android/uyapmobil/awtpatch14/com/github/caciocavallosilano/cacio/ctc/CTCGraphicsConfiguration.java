package com.github.caciocavallosilano.cacio.ctc;

import com.github.caciocavallosilano.cacio.peer.managed.FullScreenWindowFactory;
import java.awt.Dimension;
import java.awt.GraphicsConfiguration;
import java.awt.GraphicsDevice;
import java.awt.Rectangle;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.awt.image.ColorModel;
import java.awt.image.Raster;
import java.awt.image.WritableRaster;

/** JDK 14: sun.awt.image.BufferedImageGraphicsConfig final oldugu icin Cacio 1.18'deki gibi dogrudan GraphicsConfiguration. */
public class CTCGraphicsConfiguration extends GraphicsConfiguration {
    private final ColorModel model;
    private final Raster raster;
    private final CTCGraphicsDevice device;

    CTCGraphicsConfiguration(CTCGraphicsDevice device) {
        Dimension d = FullScreenWindowFactory.getScreenDimension();
        BufferedImage bi = new BufferedImage(d.width, d.height, BufferedImage.TYPE_INT_ARGB);
        this.device = device;
        this.model = bi.getColorModel();
        this.raster = bi.getRaster().createCompatibleWritableRaster(1, 1);
    }

    @Override public GraphicsDevice getDevice() { return device; }
    @Override public ColorModel getColorModel() { return ColorModel.getRGBdefault(); }
    @Override public ColorModel getColorModel(int transparency) { return ColorModel.getRGBdefault(); }
    @Override public Rectangle getBounds() {
        Dimension d = FullScreenWindowFactory.getScreenDimension();
        return new Rectangle(0, 0, d.width, d.height);
    }
    @Override public BufferedImage createCompatibleImage(int w, int h) {
        WritableRaster r = raster.createCompatibleWritableRaster(w, h);
        return new BufferedImage(model, r, model.isAlphaPremultiplied(), null);
    }
    @Override public AffineTransform getDefaultTransform() {
        double s = Double.parseDouble(System.getProperty("uyapmobil.olcek", "1"));
        return AffineTransform.getScaleInstance(s, s);
    }
    @Override public AffineTransform getNormalizingTransform() { return new AffineTransform(); }
}
