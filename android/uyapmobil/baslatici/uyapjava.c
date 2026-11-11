/*
 * uyapjava — glibc JDK 14 için en küçük Java başlatıcısı (UYAP Mobil, Android).
 *
 * Neden: Resmi Linux JDK'sının "java" başlatıcısı kurulum dizinini /proc/self/exe'den bulur; Android'de program
 * glibc bağlayıcısı üzerinden (ld-linux-aarch64.so.1 --library-path ... ) çalıştırıldığı için bu yol bağlayıcının
 * kendisi olur ve JDK bulunamaz (gerekirse yeniden exec ederken argümanlar da kaybolur). HotSpot ise java.home'u
 * libjvm.so'nun kendi konumundan bulur: bu başlatıcı libjvm.so'yu doğrudan yükleyip JNI_CreateJavaVM çağırır.
 *
 * Kullanım:  uyapjava <libjvm.so yolu> <JVM seçeneği>... -- <ana sınıf> <argüman>...
 *   JVM seçenekleri JNI biçimindedir: "-Dx=y", "-Xmx512m", "--add-opens=a/b=c", "-javaagent:yol", "-Djava.class.path=..."
 * Derleme: aarch64-linux-gnu-gcc -O2 -o uyapjava uyapjava.c -ldl -lpthread
 */
#include <dlfcn.h>
#include <jni.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef jint (JNICALL *CreateJavaVM_t)(JavaVM **, void **, void *);

struct baslat { int argc; char **argv; int ret; };

static int hata(JNIEnv *env, const char *m) {
    fprintf(stderr, "[uyapjava] %s\n", m);
    if (env && (*env)->ExceptionCheck(env)) (*env)->ExceptionDescribe(env);
    return 1;
}

static void *calis(void *p) {
    struct baslat *b = (struct baslat *) p;
    int argc = b->argc; char **argv = b->argv;
    b->ret = 1;
    void *h = dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL);
    if (!h) { fprintf(stderr, "[uyapjava] libjvm yüklenemedi: %s\n", dlerror()); return NULL; }
    CreateJavaVM_t olustur = (CreateJavaVM_t) dlsym(h, "JNI_CreateJavaVM");
    if (!olustur) { fprintf(stderr, "[uyapjava] JNI_CreateJavaVM yok\n"); return NULL; }

    int ayrac = -1;
    for (int i = 2; i < argc; i++) if (strcmp(argv[i], "--") == 0) { ayrac = i; break; }
    if (ayrac < 0 || ayrac + 1 >= argc) { fprintf(stderr, "kullanım: uyapjava libjvm.so [seçenek...] -- AnaSinif [arg...]\n"); return NULL; }

    int nopt = ayrac - 2;
    JavaVMOption *opt = calloc((size_t) nopt + 1, sizeof(JavaVMOption));
    for (int i = 0; i < nopt; i++) opt[i].optionString = argv[2 + i];
    JavaVMInitArgs va;
    va.version = JNI_VERSION_10;
    va.nOptions = nopt;
    va.options = opt;
    va.ignoreUnrecognized = JNI_FALSE;
    JavaVM *vm; JNIEnv *env;
    if (olustur(&vm, (void **) &env, &va) != JNI_OK) { fprintf(stderr, "[uyapjava] JVM oluşturulamadı\n"); return NULL; }

    /* Ana sınıf: a.b.C → a/b/C ; sistem sınıf yükleyicisiyle (classpath + -javaagent sonrası) */
    char *ad = strdup(argv[ayrac + 1]);
    for (char *c = ad; *c; c++) if (*c == '.') *c = '/';
    jclass ls = (*env)->FindClass(env, "java/lang/ClassLoader");
    jmethodID gs = ls ? (*env)->GetStaticMethodID(env, ls, "getSystemClassLoader", "()Ljava/lang/ClassLoader;") : NULL;
    jobject yukleyici = gs ? (*env)->CallStaticObjectMethod(env, ls, gs) : NULL;
    jmethodID lc = ls ? (*env)->GetMethodID(env, ls, "loadClass", "(Ljava/lang/String;)Ljava/lang/Class;") : NULL;
    jclass ana = NULL;
    if (yukleyici && lc) ana = (jclass) (*env)->CallObjectMethod(env, yukleyici, lc, (*env)->NewStringUTF(env, argv[ayrac + 1]));
    if (!ana) { b->ret = hata(env, "ana sınıf bulunamadı"); (*vm)->DestroyJavaVM(vm); return NULL; }
    jmethodID mm = (*env)->GetStaticMethodID(env, ana, "main", "([Ljava/lang/String;)V");
    if (!mm) { b->ret = hata(env, "main yöntemi yok"); (*vm)->DestroyJavaVM(vm); return NULL; }
    int nargs = argc - ayrac - 2;
    jclass sc = (*env)->FindClass(env, "java/lang/String");
    jobjectArray dizi = (*env)->NewObjectArray(env, nargs, sc, NULL);
    for (int i = 0; i < nargs; i++)
        (*env)->SetObjectArrayElement(env, dizi, i, (*env)->NewStringUTF(env, argv[ayrac + 2 + i]));
    (*env)->CallStaticVoidMethod(env, ana, mm, dizi);
    b->ret = 0;
    if ((*env)->ExceptionCheck(env)) { (*env)->ExceptionDescribe(env); b->ret = 1; }
    /* DestroyJavaVM: AWT gibi daemon olmayan iş parçacıkları bitene kadar bekler (java başlatıcısıyla aynı) */
    (*vm)->DetachCurrentThread(vm);
    (*vm)->DestroyJavaVM(vm);
    free(ad);
    return NULL;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "kullanım: uyapjava libjvm.so [seçenek...] -- AnaSinif [arg...]\n"); return 2; }
    /* JVM'i büyük yığınlı ayrı bir iş parçacığında başlat (java başlatıcısının yaptığı gibi; ana iş parçacığı yığını küçük olabilir) */
    struct baslat b = { argc, argv, 1 };
    pthread_attr_t a;
    pthread_attr_init(&a);
    pthread_attr_setstacksize(&a, 8 * 1024 * 1024);
    pthread_t t;
    if (pthread_create(&t, &a, calis, &b) != 0) { calis(&b); return b.ret; }
    pthread_join(t, NULL);
    return b.ret;
}
