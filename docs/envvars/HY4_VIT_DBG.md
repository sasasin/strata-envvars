# `HY4_VIT_DBG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Apple Metal 版 HY4-Flash の画像 ViT encoder において、中間値の診断出力を有効にする。`VitMetal::dbg` が true のとき、画像を `VitMetal::encode` で符号化する際に第0層の複数の buffer を走査し、非有限値の個数と RMS を stderr に出す。生成や attention の選択を変える設定ではなく、診断走査とログを加えるフックである。実装は `engine/src/hy4flash/metal/hy4_metal_vision.h` にある（同ファイル:149-166, 218-255）。

この変数の完全一致参照は同ファイル:149 のみで、`getenv` を直接呼び出す。共通 helper や動的な変数名を介した読み取りはない。

## 値と判定

環境変数の値は変換・比較されず、`getenv("HY4_VIT_DBG") != nullptr` の有無だけを見る。設定されていれば空文字、`0`、`false`、任意の文字列を含めて true、未設定なら false。数値としての妥当性・大文字小文字・空白・範囲は判定しない（同ファイル:149）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal 版 HY4-Flash の `VitMetal` | false | 空文字、`0`、`false`、`1`、その他、設定された任意の値 | なし（値が存在すれば有効） |

## 有効になる条件

- `VitMetal` が組み込まれた HY4-Flash Metal 実行経路であること。このコードは `engine/src/hy4flash/metal/` にあり、Metal の `VitMetal` 実装である（`hy4_metal_vision.h:1-3, 46-60`）。
- 画像を ViT encoder に渡して `VitMetal::encode` が呼ばれること。オフライン実行では画像レコードがある場合に encoder をロードして `VisionCtxM::setup` が画像ごとに `encode` を呼ぶ（`hy4_metal_main.cpp:1773-1782`; `hy4_metal_vision.h:306-318`）。serve では encoder オブジェクト自体は serve 初期化時に作られるが、画像付きリクエストで encoder をロードし `setup` した場合に encode される（`hy4_metal_serve.h:292-300, 365-373`）。
- `HY4_VIT_ATTN` によって MPP attention 経路が選ばれない場合に限り、`ln0 (d_h)`・`q`・`k`・`v` の4検査も実行する。`HY4_VIT_ATTN` 未設定時または値が厳密に `mpp` のときは MPP 経路となり、その4検査は省略される。それ以外の値では MPP 以外の経路となる（`hy4_metal_vision.h:199-202, 224-226`）。
- attention 経路にかかわらず、最初の ViT 層 (`il == 0`) で `attn out`、`x after o_proj`、`ln2`、`ff after fc1` の検査を行う。第1層以降ではこのデバッグ検査は行わない（`hy4_metal_vision.h:218-225, 247-255`）。

## 実行時の詳細

`dbg` は `VitMetal` の非 static データメンバー初期化子で `getenv` を呼ぶため、各 `VitMetal` インスタンスの構築時に一度読み取られる。serve では serve ループ開始前に encoder を構築し、オフライン実行でも `recs.empty()` の判定前に構築する。インスタンス構築後に環境を変更しても、そのインスタンスの値は変わらない（`hy4_metal_vision.h:46-60, 149`; `hy4_metal_main.cpp:1773-1777`; `hy4_metal_serve.h:292-300`）。

`nan_check` は指定された buffer を要素ごとに走査する。FP16 buffer は符号・指数・仮数から float 値に復元し、FP32 buffer はそのまま読み、`std::isfinite` が false の要素数と有限要素の二乗平均平方根を計算する。各呼び出しにつき `[vit dbg] %s: %zu non-finite of %zu, rms %.4f\n` の書式で stderr に出す。`x after o_proj` と `ln2` / `ff after fc1` の検査前には dispatch queue を `flush("dbg")` する。これは buffer の検査タイミングを確保する処理である（`hy4_metal_vision.h:83-89, 149-166, 247-253`）。

## ログと測定値

有効な検査が実行されるごとに、stderr に `[vit dbg] <対象名>: <非有限値数> non-finite of <要素数>, rms <小数4桁>` 形式の1行が出る。未設定時、画像 encode が行われない場合、第0層の検査箇所まで到達しない場合は出ない。`HY4_VIT_ATTN=mpp` または未設定時は `ln0 (d_h)`・`q`・`k`・`v` の行だけが出ない。対象変数に関する性能測定値は Strata の資料に見当たらない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_vision.h:46-60, 149-166` — `VitMetal` と変数読み取り、buffer 検査・ログ。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:199-202, 218-255` — attention 経路判定と第0層での検査位置。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:306-318` — 画像ごとの encode 呼び出し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782` — offline の画像経路。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:292-300, 365-373` — serve での encoder 構築と画像リクエスト経路。
- `docs/DETAILS.md:1113-1148` — 画像・vision の一般説明。`HY4_VIT_DBG` 固有の説明や測定値は記載されていない。
