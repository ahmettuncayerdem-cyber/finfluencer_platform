# Hakem Raporu — finfluencer_tr_2025_BIR_Methods_Results_FINAL_with_discussion.docx

Tamamı okundu: başlık, Giriş, Kavramsal Çerçeve (2.1–2.8), Yöntem (3.1–3.9), Bulgular (4.1–4.8), Tartışma (5.1–5.3), Sonuç, Kaynakça. Bu rapor, BIR için gerçekten nasıl puanlayacağım şekilde yazıldı, yumuşatılmadı.

## Genel değerlendirme

Ampirik çekirdek sağlam — gerçek veri, gerçek sayılar, nedensellik konusunda dürüst temkinlilik, mantıklı sağlamlık (robustness) kontrolleri. Ancak makale şu anki haliyle **gönderime uygun değil**. Anında fark edilen ölümcül bir kusur var (Bölüm 5.3) ve dikkatli bir editörden resmi bir "bu ne böyle" sorgusu getirecek ikinci dereceden bir sorun (bozulmuş atıflar) var — sadece revize-et-tekrar-gönder değil. İkisi de mekanik ve bir saatten kısa sürede düzeltilebilir; ikisi de altta yatan araştırmayı kötü yansıtmıyor. Ama bu haliyle gönderilirse, bir hakem Bulgular'a ulaşmadan, 8. sayfada masadan geri çevrilir.

---

## 1. Masadan-ret seviyesinde kusur

**Makale gövdesinin içinde bırakılmış AI düzenleme değişiklik günlüğü (changelog).** Bölüm 5.3'ün (Sınırlılıklar ve Gelecek Araştırmalar) hemen ardından ve "6. Sonuç"tan önce, altı paragraflık saf meta-yorum, sanki normal makale metniymiş gibi karşımıza çıkıyor:

> "Replaced the literature-restating opening with a contribution-led framing that preserves both the central message-messenger claim and the secondary, confirmatory status of the market-integration extension." (Literatürü tekrar eden girişi, hem merkezi mesaj-mesajcı iddiasını hem de piyasa-entegrasyonu uzantısının ikincil/doğrulayıcı statüsünü koruyan katkı-odaklı bir çerçeveyle değiştirdim.)
> "Converted the empirical-style result recap into a theoretical interpretation paragraph, eliminating all numerical repetition." (Ampirik tarz sonuç özetini, tüm sayısal tekrarları ortadan kaldıran teorik bir yorum paragrafına dönüştürdüm.)
> "Added explicit subsections for theoretical contribution, practical implications, limitations, and future research, in the order requested, populated only with material already present in the manuscript." (Teorik katkı, pratik çıkarımlar, sınırlılıklar ve gelecek araştırmalar için, istenen sırada, yalnızca makalede zaten var olan malzemeyle doldurulmuş açık alt bölümler ekledim.)
> ...ve aynı üslupla üç paragraf daha.

Bu, Tartışma bölümünde yapılan düzenlemeleri anlatan bir değişiklik günlüğü — açıkça bu dosyaya en son dokunan aracın ürettiği bir metin — ve çevresindeki paragraflarla aynı biçimde, sanki düzyazıymış gibi makalenin içinde duruyor. Herhangi bir editör veya hakem bunu ilk okumada fark eder. Bu ya ciddi bir dikkatsizlik olarak okunur ya da daha kötüsü, belgenin geri kalanının ne kadarının nihai bir insan gözden geçirmesi olmadan aynı denetimsiz süreçten geçtiği sorusunu akla getirir. **Başka hiçbir şeyin önemi olmadan önce bu silinmelidir.**

---

## 2. Kaynakça bozulması — kozmetik değil, gerçek bir sorun

Kaynakça bölümü, düzyazı tamamlandıktan sonra bir noktada açıkça bir atıf yöneticisi (citation manager) tarafından yeniden üretilmiş (her girişte hâlâ EndNote paragraf stili etiketli) ve bu yeniden üretim, bu literatürdeki bir uzman hakemin ilk bakışta tanıyacağı isimleri bozmuş.

- **"Long, J. B. D., Shleifer, A., Summers, L. H., & Waldmann, R. J. (1990)"** — bu, De Long, Shleifer, Summers ve Waldmann'ın alandaki en çok atıf alan makalelerinden biri olan *Noise Trader Risk in Financial Markets* çalışması. Ayrıştırıcı (parser), "De Long"u sanki bir orta isim baş harfiymiş gibi bölüp "De"yi düşürmüş, "Long, J. B. D." haline getirmiş. Makale boyunca (Giriş, Kavramsal Çerçeve, Tartışma) tüm metin-içi atıflar artık "De Long et al. (1990)" yerine "Long et al. (1990)" şeklinde. Bu tür bir hata, hakeme kaynakçanın literatürü bilen bir insan tarafından hiç kontrol edilmediği sinyalini verir.
- **"Horton, D., & Richard Wohl, R. (1956)"** — R. Richard Wohl'un isminde aynı bozulma türü; kaynakçada isim ters yazılmış ("Wohl, R. R." yerine "Richard Wohl, R."), ve Bölüm 2.4 boyunca metin-içi atıf "Horton and Richard Wohl (1956)" şeklinde — hem garip hem yanlış.
- **Hovland, Janis, & Kelley (1953)** kaynakça girişi alt başlık ve yayınevi olmadan "Communication and persuasion." şeklinde kısaltılmış (doğrusu *Communication and persuasion: Psychological studies of opinion change*, Yale University Press olmalı).
- **Bir atıf yanlış kaynağa bağlanmış.** Bölüm 2.5, iki ayrı bulguyu "Tversky and Kahneman (1974)"a atfediyor: sezgisel yargı-önyargı bulgusu (doğru) ve "resulting choices depart from expected-utility predictions in framing-sensitive ways" (yanlış — bu, Kahneman ve Tversky'nin 1979'da Econometrica'da yayımlanan Beklenti Teorisi/Prospect Theory bulgusu). 1979 makalesi hiçbir yerde atıf almıyor ve kaynakçada da yer almıyor. Bu bir biçimlendirme hatası değil; gerçek bir bulgu yanlış yayına atfedilmiş.
- **İki atıf, uydurma olmayan ama farklı gerçek makalelerle sessizce değiştirilmiş** ve destekledikleri cümleyle yeniden doğrulanmamış:
  - Medya zenginliği/sosyal varlık teorisi artık Daft & Lengel (1986) *ve* Fortunati & Manganelli (2008)'e atfediliyor — ikincisi telekomünikasyonun sosyal temsilleri üzerine gerçek bir 2008 *Personal and Ubiquitous Computing* makalesi, ama argümanın aslen üzerine kurulduğu klasik sosyal-varlık atfı (Short, Williams, & Christie, 1976) değil, ve kimsenin Fortunati & Manganelli'nin gerçekte ne iddia ettiğini, şimdi bağlandığı cümleyle örtüşüp örtüşmediğini kontrol ettiği görülmüyor.
  - Sürü davranışı/bilgi kademeleri (informational cascades) artık "Bikhchandani, Hirshleifer, & Welch (2018)" — aynı üç yazarın gerçek bir 2018 Palgrave Dictionary of Economics girişi, ama bu literatürde "informational cascades" denince akla gelen 1992 tarihli ünlü *Journal of Political Economy* makaleleri değil. Orijinal teorik makale yerine ansiklopedi girişine atıf yapmak savunulabilir ama alışılmadık bir tercih ve bir hakem bunu sorgular.
  - İki-aşamalı akış (two-step-flow) atfı artık "Katz, Lazarsfeld, & Roper (2017)" — *Personal Influence*'ın gerçek bir Routledge yeniden basımı, ama bu literatürdeki her diğer makale (bu projenin kendi önceki taslakları dahil) 1955 orijinaline atıf yapıyor. Yeniden basıma atıf yapmak tek başına sorun değil; çevredeki literatürle tutarsız biçimde yapmak sorun.

Bu beşinin hiçbiri uydurma atıf değil — bu tek iyi haber, ve Giriş'in daha önceki bir taslağına göre gerçek bir iyileşme (o taslakta doğrulanamayan atıflar vardı, burada doğru şekilde yok). Ama "uydurma değil" düşük bir eşik. Şu anda kaynakça listesi, atıf yapılan makaleleri okumuş herhangi bir ortak yazarın beş dakikalık nokta kontrolünden geçemez.

---

## 3. Hakemin hemen fark edeceği bir iç-tutarlılık hatası

Bölüm 4.7 şöyle başlıyor: **"Table 7 summarises seven robustness checks."** (Tablo 7 yedi sağlamlık kontrolünü özetlemektedir.) Ardından tam olarak dördünü ele alıyor ("İlk olarak... İkincisi... Üçüncüsü... Dördüncüsü...") ve **"Across all four checks, the central finding... is confirmed"** (Dört kontrolün tamamında, merkezi bulgu... doğrulanmaktadır) diyerek kapanıyor. Bölüm dört mü yedi mi kontrol yapıldığına karar veremiyor. Eğer üç kontrol var ama yazıya dökülmemişse, bu bir yazım hatasından daha büyük bir sorun — makalenin, gösterimini yapmadığı bir sağlamlık testini iddia ettiği anlamına gelir. Bu, altta yatan analiz çıktılarına karşı hangisinin gerçekten doğru olduğu doğrulanana kadar "seven"i "four" ile değiştirmekten daha kesin bir düzeltme gerektirir.

---

## 4. Önemli metodolojik baskı noktaları (ölümcül değil, ama bir hakem hepsine yüklenir)

- **"Sağlam" olan tek bulgu, konu dağılımı en yoğunlaşmış analiste ait.** Bölüm 4.7'nin kendi HHI sağlamlık kontrolü, Şatıroğlu'nun diğer üç analiste kıyasla (0.053–0.077) belirgin biçimde daha konu-yoğunlaşmış olduğunu (HHI=0.129) gösteriyor — ve Şatıroğlu aynı zamanda mesajcı etkisi her üç tahmin yönteminde de ayakta kalan *tek* analist. Makalenin kendi Bölüm 2.6'sı, 128 ayrık konunun kaynak kimliğinden konu-içi çerçevelemeyi tam olarak ayıramayabileceğini teorik bir sınırlılık olarak belirtiyor. Ancak ampirik olarak, Şatıroğlu'nun "sağlam mesajcı etkisi"nin kısmen, daha kaba veya daha ince bir konu ayrıntı düzeyinde zayıflayacak bir kalıntı konu-seçim etkisi olmadığını hiçbir yerde dışlamıyor. Bu alt alandaki bir hakem, sadece bir genel (omnibus) sağlamlık tablosu değil, konu ayrıntı düzeyini özellikle Şatıroğlu karşıtlığıyla etkileşime sokan bir spesifikasyon isteyecektir.
- **Merkezi "mesajcı etkisi" iddiası dört analistten tam olarak birine genelleniyor.** Geçer, naif ve karma-model (mixed-model) spesifikasyonlarında anlamlı ama kümelenmiş-sağlam (cluster-robust) standart hatalarda değil; Yeşilada naif ve kümelenmiş-sağlam spesifikasyonlarda anlamlı ama karma modelde değil. Sadece Şatıroğlu her yerde ayakta kalıyor. Özet ve Sonuç bölümleri "iletişimci kimliği"ni genel ifadelerle "istatistiksel olarak anlamlı" diye tanımlıyor; dikkatli bir okuyucu bunun Tablo 7'nin gerçekte gösterdiğine kıyasla abartılı olduğunu fark edecektir. Bu, mesajcı etkisinin iddia edildiği her yerde — sadece sağlamlık tablosunun dipnotunda değil — Şatıroğlu'na özgü iddianın dışında açıkça nitelendirilmelidir.
- **Yeşilada'nın alt örneklemi son derece ince** — 8 video, 510 yorum, diğer üçü için 93–99 video ve 3.600–8.200 yorumla kıyaslandığında. Yeşilada içeren her analistler-arası karşılaştırma, iyi güçlendirilmiş bir tahmini zar zor güçlendirilmiş bir tahminle karşılaştırıyor. Bu durum açıklanmış ama Yeşilada içeren karşılaştırmaların metinde ne kadar güvenle ele alındığına kıyasla yeterince ağırlıklandırılmamış (ör. "Başaran–Yeşilada, p=.013" 4.2'de altta yatan örneklem asimetrisine dair hiçbir uyarı olmadan temiz, anlamlı bir ikili karşılaştırma olarak sunuluyor).
- **Duygu sınıflandırıcısı finans alanına uyarlanmamış genel amaçlı bir Türkçe BERT modeli**, sadece 462 altın-standart ikili etikette doğrulanmış (MCC=0.719 — makul, olağanüstü değil) ve gerçek bir nötr sınıf olmadan pozitif/negatif ikiliğe zorlanmış. %6.8'lik "sözde-nötr" bant belirtilmiş ama ana bulgularda farklı davranıp davranmadığı hiç analiz edilmemiş — kabul edilip sonra bırakılmış.
- **Figür 2'nin kendi başlık yazısı, Giriş'in beşinci katkısındaki "tam olarak yeniden üretilebilir işlem hattı" iddiasını zayıflatıyor**: başlık yazısı, kanonik BERTopic konular-arası mesafe haritasının üretilemediğini çünkü "the cached embedding index required for the latter was unavailable at analysis time" (gerekli önbelleğe alınmış gömme (embedding) indeksinin analiz zamanında mevcut olmadığını) belirtiyor. Başlıca bir figür için gerekli bir çıktı istendiğinde yeniden üretilemiyorsa, bu sadece bir figür dipnotunda değil, Sınırlılıklar'da bir cümleyi hak eder — ve tam yeniden üretilebilirlik iddia eden bir katkılar paragrafının yanında garip duruyor.
- **17.566 yorumdan 128 konu (~konu başına ortalama 137 yorum, bazı bildirilen konularda n=33–52) bu külliyat büyüklüğü için oldukça fazla konu sayısı.** Tablo 3'teki başlıca etki büyüklüklerinin birçoğu, FDR düzeltmesinin yanlış-keşif oranını kontrol ettiği ama tek tek Cohen's h tahminlerinin hassasiyetini kurtarmadığı kadar küçük hücrelerden geliyor. Tablo 3 etki büyüklükleri için sadece nokta tahminleri değil, metinde doğrudan güven aralıklarının da bildirilmesi gerekir.

## 5. Makalenin iyi yaptığı şeyler (adil bir hakem bunu da söyler)

Granger-nedensellik çerçevelemesi gerçekten disiplinli — "geçici öngörülebilirlik, ekonomik nedensellik değil" ifadesi, Sonuç dahil, konu her geçtiğinde doğru şekilde tekrar tekrar belirtiliyor; bu literatürde olması gerekenden daha nadir bir titizlik. Piyasa-entegrasyonu bölümü baştan sona dürüstçe doğrulayıcı ve ikincil olarak konumlandırılmış, hiç abartılmamış. İnsan-doğrulama protokolü (kör kodlayıcılar, üçüncü taraf hakemliği, önyükleme (bootstrap) güven aralıkları, önceden kayıtlı κ eşiği) finans dergilerindeki çoğu duygu-analizi makalesinden daha titiz. Varyans-ayrıştırma mantığı (konu vs. analist, sıralı kısmi R², karma-model LR testlerine karşı çapraz doğrulanmış) araştırma sorusu için doğru tasarım ve sunulan sayılar dahilinde iç tutarlılık açısından doğru uygulanmış.

## 6. Gönderim öncesi düzeltme öncelik sırası

1. Bölüm 5.3'ün sonundaki altı değişiklik-günlüğü paragrafını sil. Pazarlık konusu değil, beş dakika, önce bunu yap.
2. "Long et al."ı "De Long et al." ile, "Horton and Richard Wohl"u "Horton and Wohl" ile her yerde (metin-içi ve kaynakçada) düzelt.
3. Tversky & Kahneman (1974) çifte-atfını çöz: ya çerçeveleme-etkisi iddiasını çıkar ya da Kavramsal Çerçeve belgesi için zaten doğrulanmış ana kaynakça listesiyle eşleşecek şekilde Kahneman & Tversky (1979)'u düzgünce ekle.
4. Fortunati & Manganelli (2008) ile Bikhchandani, Hirshleifer, & Welch (2018)'in gerçekten bağlı oldukları belirli iddiaları destekleyip desteklemediğini yeniden doğrula — sadece gerçek DOI'ler olduklarına güvenme, cümlenin söylediğini gerçekten söylediklerini teyit et.
5. "Yedi sağlamlık kontrolü" ile "dört kontrol" çelişkisini gerçek analiz çıktılarına karşı çöz.
6. Özet/Tartışma/Sonuç'ta "iletişimci kimliği anlamlıdır" iddia edilen her yere, bunun dört analistin tamamı için değil, dördünden biri için sağlam biçimde geçerli olduğuna dair açık bir nitelendirme ekle.
