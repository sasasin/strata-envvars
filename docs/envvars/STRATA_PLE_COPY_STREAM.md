# `STRATA_PLE_COPY_STREAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリや GPU driver の環境変数の動作は対象外です。

## 役割

prompt prefill の PLE（prompt lookup embeddings）行を、compute stream ではなく専用の非ブロッキング stream から GPU に転送する opt-in 設定です。対象は PLE 行を IQ4_NL raw bytes のまま転送し、GPU 上で dequantize する経路です。転送を layer 0 の計算と重ね、layer 1 が PLE 行を使う時点で compute stream に転送完了を待たせます。

この変数だけでは raw-row 経路を有効にしません。通常は `STRATA_PLE_COMPACT` も有効で、raw device buffer の確保と raw-row gather が成功する必要があります。条件を満たさない場合は従来の float 行転送となり、この専用 stream は使われません。

## 値と判定

`std::getenv` の結果について、未設定でないことと先頭文字が `'1'` であることだけを判定します。値全体の parse、数値変換、範囲検査はありません（`src/prefill/prefill.cpp:162-165`）。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF（値は設定済みだが先頭文字が `\0`） |
| `1`, `10`, `1anything` | ON |
| `0`, `true`, ` 1`, その他先頭文字が `1` でない値 | OFF |

判定結果は関数内 `static const bool` に保存されます。プロセス内で最初に `ple_copy_stream_on()` が呼ばれた後に環境を変更しても再評価されません。CLI 引数や設定ファイルによる上書き経路はこの変数について見つかりません。

## 有効になる条件

専用 stream が作成され、実際の raw-row upload に使われるには、次の条件が必要です。

- Strata の GPU prefill 経路を使うこと。`strata_prefill` は CUDA または HIP backend の GPU build で構成されます（`CMakeLists.txt:412-420,815-825`）。この環境変数に独立した OS・GPU 世代判定はありません。
- PLE が利用可能で、実行範囲が layer 1 を含むこと。通常の chunk 経路では `ss.ple.ready() && LB <= 1 && 1 < LE` が PLE 使用条件です（`src/prefill/prefill.cpp:3044-3048`）。
- `STRATA_PLE_COMPACT` が有効で raw-row buffer を確保できること。raw device buffer がない場合、copy stream の作成条件を満たしません（`src/prefill/prefill.cpp:154-158,1693-1699,1702-1706`）。
- PLE の host buffer が pageable fallback ではなく、`gather_raw_iq4nl()` が raw rows を取得できること。いずれかを満たさなければ通常の float gather に戻ります（`src/prefill/prefill.cpp:3069-3077`）。

したがって、変数が ON でも `STRATA_PLE_COMPACT` が OFF、PLE が不在、raw buffer の確保失敗、pageable host buffer の使用、または raw gather 不成立なら専用 stream は使われません。`STRATA_PLE_COMPACT` の値判定も先頭文字 `'1'` であり、別の static cache です。

## 実行時の詳細

chunk 用リソース初期化時に raw buffer が存在し、変数が ON なら `cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` と `ple_raw_free` event の作成を試みます。どちらかが失敗すると stream を破棄して null に戻し、stderr に次の警告を出します。その後の転送は compute stream 上で続きます（`src/prefill/prefill.cpp:1702-1710`）。

raw-row chunk の upload では専用 stream が前 chunk の dequant 完了 event `ple_raw_free` を待ってから raw bytes を転送します。compute stream は upload 完了 event `ple_copied` を待って dequant を実行し、dequant 後に `ple_raw_free` を記録します。これにより raw buffer の再利用前に前 chunk の読み取りが終わり、upload は layer 0 の計算と重なる設計です（`src/prefill/prefill.cpp:3247-3273`）。二つの PLE buffer を交互に使い、次の chunk を用意する前に反対側 buffer の upload event を同期します（`src/prefill/prefill.cpp:3274-3285`）。

upload、stream/event wait、または dequant 後の event 記録が失敗すると `run_impl` は `false` を返し、`err` に `prefill: the PLE rows' upload failed: ...` を設定します（`src/prefill/prefill.cpp:3255-3271`）。`Prefill::run` は `false` を返し、`strata generate` の呼び出し元はエラーを表示して処理を中断します（`src/prefill/prefill.cpp:7271-7276`, `src/program/generate.cpp:17795-17800`）。prompt 実行の早期 return 時にも `KvDrain` が専用 stream を同期してから戻ります。同期自体の失敗値はこの destructor では確認されません（`src/prefill/prefill.cpp:2993-2998`）。リソース破棄時には専用 stream と event を破棄します（`src/prefill/prefill.cpp:1248-1252`）。

通常の有効化ログはありません。stream または event を作成できなかった場合の警告文は `prefill: STRATA_PLE_COPY_STREAM=1: the upload stream could not be created, the PLE rows go up on the compute stream` です（`src/prefill/prefill.cpp:1710`）。`docs/DETAILS.md` は `STRATA_PLE_COMPACT=1`, `STRATA_PLE_COPY_STREAM=1`, `STRATA_EMBED_VRAM=1`, `STRATA_DEQUANT_SIDE=1` の4設定をまとめて、prompt の +2.2%～+2.6% と記載しています。これは4設定を合わせた報告値で、個別の本変数の効果を示す測定値ではありません（`docs/DETAILS.md:1546`）。

## 根拠

- 値判定と cache: `src/prefill/prefill.cpp:160-165`
- PLE 状態と compact gather 条件: `src/prefill/prefill.cpp:3044-3048,3069-3077`
- raw buffer、stream/event 作成と失敗時 fallback: `src/prefill/prefill.cpp:1693-1710`
- 専用 stream での upload、同期、dequant、失敗経路: `src/prefill/prefill.cpp:3247-3285`
- chunk 終了・早期 return 時の drain と resource cleanup: `src/prefill/prefill.cpp:2993-2998,1248-1252`
- GPU backend の prefill library 構成: `CMakeLists.txt:412-420,815-825`
- 4設定をまとめた性能報告: `docs/DETAILS.md:1546`
