# `STRATA_GDN_CHUNKED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の GDN（gated delta network）prompt prefill における recurrence を、従来の token ごとのカーネルではなく、32 token のチャンクをまとめて処理する CUDA カーネルに切り替えます。環境変数は `src/prefill/kernels.cu` の `gdn_recurrence_variant()` で読み取られます。呼び出し元は GDN 層の prefill 処理です（`src/prefill/prefill.cpp:2603-2624`）。

## 値と判定

両方の読み取り箇所で `std::atoi()` を使います。文字列全体の妥当性検査はなく、先頭の整数として変換できる部分が判定に使われます。未設定、空文字、整数として始まらない文字列は `atoi` の結果が 0 です。たとえば `1tail` は 1、`2tail` は 2、`-1` は -1 として扱われます。

| 値（`atoi` の結果） | recurrence の切り替え | 128 SM 未満のカードで SM 数制限を外す |
|---|---|---|
| 未設定、0 | しない | しない |
| 0 以外、2 未満（例: `1`, `-1`） | 試みる | しない |
| 2 以上（例: `2`, `3`） | 試みる | する |

`chunked` の判定は `gdn_recurrence_variant()` 内の `static const bool` に保存されます。SM 数制限を外す `any_sms` も `gdn_rec_chunked()` 内の別の `static const bool` で初回評価時に保存されます。通常のプロセス起動後に環境変数を変更しても、評価済みの判定は更新されません。

## 有効になる条件

環境変数を有効にしても、次の条件を満たさなければ chunked カーネルは使われません。

- CUDA ビルドであること。切り替えと chunked 実装は `#if !defined(__HIPCC__)` の範囲にあり、HIP ビルドではこの環境変数を使いません。
- `STRATA_GDN_REC_HEADS` が設定されていないこと。これは値の内容ではなく設定有無で通常の別カーネルを選ぶ条件です。
- 呼び出しの `T` が 128 以上であること。短い prompt chunk では従来経路になります。
- GPU の compute capability major が 8 以上であること。
- 通常値（`atoi` 結果が 2 未満）では、SM 数が `HK * (S / GDV)` 以上（この実装のコメント上は 128 SM）であること。`atoi` 結果が 2 以上ならこの SM 数条件だけを外します。
- opt-in shared memory が chunked scan の必要量 `kChunkScanSmem` 以上であること。値 2 以上でも architecture と shared-memory 条件は残ります。
- GPU ごとの scratch buffer の確保に成功すること。

条件を満たさない場合、または scratch 確保に失敗した場合、`gdn_rec_chunked()` はエラーを返し、呼び出し側は従来の GDN recurrence カーネルに切り替えます。通常経路では `STRATA_GDN_PIPELINE` の設定と GPU 条件に応じて key-head カーネル、software-pipelined カーネル、または通常カーネルが選ばれます。

## 実行時の詳細

chunked 経路は 32 token のチャンクを最大 2048 token の super-block にまとめます。各 super-block について prep と scan の CUDA kernel を起動し、scan が gated delta rule の recurrence と状態更新を行います。その後、通常経路と同じ出力正規化 kernel が起動します。ソースコメントは chunked 演算が既定経路と同じ状態・出力を FP32 の加算順序による丸め差の範囲で得ると説明しています（`src/prefill/kernels.cu:714-725,1017-1062,1980-1992`）。

scratch はデバイスごとに初回使用時に `cudaMalloc` で確保され、以降保持されます。最大 25.6 MB とソースに記載されています。device 属性の取得失敗、GPU 条件不一致、scratch 確保失敗では chunked 経路から戻り、呼び出し側が別カーネルを起動します。chunked 用のログ出力はこの経路にありません。最終 kernel launch のエラーは `check("gdn_recurrence")` の既存エラー処理に渡されます。

`STRATA_GDN_CHUNKED=2` は通常の実行条件を無条件に無視する設定ではなく、SM 数チェックだけを無効にして、小さいカードでも測定用に試行する値です。

## 文書の説明と測定値

`docs/DETAILS.md:1668-1679` はこの切り替えを opt-in と記載し、RTX 5090 では recurrence が 1.8 倍、RTX 3060（28 SM）と RTX 5070（48 SM）では値 2 による強制実行が遅く、prompt time も改善しなかったと報告しています。同節にある測定方法は、切り替え前後の engine run を交互に行い、3つの固定 prompt で 200 token の greedy answer を使った比較です。これらは文書に記録された測定結果であり、ここで再計測した値ではありません。

## 根拠

- 読み取り、既定経路への fallback、HIP 除外: `src/prefill/kernels.cu:1974-1994`
- 128 token の閾値: `src/prefill/kernels.cu:729,1980-1984`
- GPU 条件、`=2` の SM 数条件緩和、scratch 確保: `src/prefill/kernels.cu:999-1062`
- chunked recurrence の方式: `src/prefill/kernels.cu:714-738`
- prefill 側からの GDN 呼び出し: `src/prefill/prefill.cpp:2603-2627`
- 文書記載の性能と測定条件: `docs/DETAILS.md:1668-1679`
