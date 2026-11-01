# `DS4_TIMELINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek 実行ファイル `strata_ds4` の遅延 dispatch を GPU timestamp 付きで記録し、プロセス終了時に kernel ごとの GPU 実行時間と dispatch 間の gap を stderr に集計する診断用スイッチです。設定されると、対象 dispatch を個別の compute encoder に分ける処理も有効になります。通常の Qwen 向け `strata` や CUDA/HIP/SYCL ビルドでは、この判定コードは有効になりません。

## 値と判定

値を文字列比較・数値変換せず、`std::getenv("DS4_TIMELINE")` が null かどうかだけを判定します。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効。記録開始処理を登録しない |
| 空文字を含む設定済み値 | 有効 |
| `0`、`false`、その他の任意の文字列 | 有効 |

CLI 引数や別環境変数による `DS4_TIMELINE` 自体の上書き・優先順位はありません。読み取りは `Context` の構築時で、最初の有効な `Context` で一度だけ `atexit` レポートを登録します。グローバル状態 `g_tl` はプロセス内に保持されます。

## 有効になる条件

- macOS の Metal ビルドで `strata_ds4` を使うこと。`metal/CMakeLists.txt` は macOS 以外の構成を拒否し、`strata_ds4` 用の runtime コピーを `STRATA_DS4_RUNTIME` 付きでコンパイルします。この macro のない通常の Metal runtime や他 backend にはこの機能が入りません。
- 実際に記録されるのは `Context::run()` が `ds.size() == 1 && reps == 1 && !barrier_between` の遅延経路に入った dispatch です。まとめて実行する経路には timestamp encoder を付けません。
- GPU が Metal timestamp counter set と counter sample buffer を提供する必要があります。counter set がない場合は `mtl: DS4_TIMELINE: no timestamp counter set`、sample buffer を作れない場合は `mtl: DS4_TIMELINE: no counter sample buffer` を stderr に出し、timeline を無効にして通常 encoder を使います。
- `DS4_TL_DRAFT` が設定されている場合は、`ds4_main.cpp` の speculative draft 処理中だけ timeline gate を開きます。これも値の内容ではなく設定有無で判定します。

## 実行時の詳細

有効な場合、遅延経路は `tl_make_encoder()` で timestamp sample slot 付き encoder を作り、各 dispatch の pipeline 名を対応する slot に記録します。また `g_tl.on` が真なので、`DS4_ENC_EACH` が未設定でも dispatch ごとに encoder を閉じて次を作ります。記録上限は最初に確保できた sample 数 `per` の 120 倍です。後続 sample buffer の追加に失敗すると、その時点で上限を記録済み件数まで縮め、以降は通常 encoder に戻します（この追加失敗には専用ログがありません）。

終了時の `atexit` 処理は、記録件数が 2 未満ならレポートを出しません。timestamp 解決に失敗した場合は `mtl: DS4_TIMELINE: resolve failed` を stderr に出して集計を中止します。それ以外では `timeline:` 行として総 dispatch 数、wall/busy/gap 時間、重複 dispatch 数と、最大 40 kernel の集計を出します。`DS4_TL_FROM` は出力集計の開始 index を `atoll` で読み、未設定時は 0 です。`DS4_TL_AFTER` は計測を開始する dispatch 数を `atol` で読み、未設定時は 0 です。これらは `DS4_TIMELINE` の値判定とは別の補助変数です。

## 根拠

- macOS 限定と Metal build 条件: `metal/CMakeLists.txt:1-2,16-18,151-169`。
- `DS4_TIMELINE` の有無判定、プロセス終了時レポート登録: `metal/src/mtl_rt.mm:292-305`。
- counter set / sample buffer の確認、警告、記録上限と補助変数: `metal/src/mtl_rt.mm:95-153`。
- 遅延 dispatch 経路、pipeline 名の記録、encoder 分割: `metal/src/mtl_rt.mm:902-957`。
- 終了時集計、stderr の出力形式と resolve 失敗: `metal/src/mtl_rt.mm:156-213`。
- `DS4_TL_DRAFT` による gate の有効区間: `src/dsv41/ds4_main.cpp:202-208,223-235`。
