# `STRATA_EMBED_VRAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

ネイティブ (IQ) pack の `token_embd.weight` を、通常の mapped pinned host memory ではなく、条件を満たす場合に現在の GPU の VRAM へ置くための opt-in です。表のバイト列は変換せずコピーされ、どちらの配置でも gather は同じ `dev_` ポインターから読みます。環境変数が変えるのは配置先であり、埋め込み値の計算形式ではありません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | VRAM 配置を要求しない。 |
| 空文字 | 設定済みだが先頭文字が `\0` のため要求しない。 |
| 先頭文字が `1` | VRAM 配置を試す。例: `1`, `10`, `1anything`。 |
| その他の文字列 | 要求しない。例: `0`, `true`, ` 1`。 |

文字列全体の比較、数値変換、大文字小文字変換はありません。無効な値を警告する処理もなく、通常の mapped host memory の配置へ進みます。CLI 引数や別の環境変数による上書きはありません。

## 有効になる条件

- `NativeEmbed::load()` が呼ばれる必要があります。通常の canonical pack ではなく `native_pack` の経路で実行される場合に限り、生成処理がこのロードを行います。
- CUDA 系 `src/core/native_head.cpp` の実装でこの変数を読みます。SYCL 側の対応する `sycl/src/core/native_head.cpp` にはこの環境変数の読み取りがなく、同じネイティブ pack のロードでもこの opt-in は適用されず、mapped host memory を先に試します。
- CUDA 側で値が有効でも、`cudaMemGetInfo()` が成功し、空き VRAM がテーブル全体のサイズに 512 MiB を加えた量を**超え**、さらに `cudaMalloc()` とホストからの `cudaMemcpy()` が成功した場合にだけ要求した VRAM 配置になります。等しい場合は条件を満たしません。
- 空き量の不足、空き量取得失敗、VRAM 確保失敗、またはコピー失敗では要求配置を採用せず、mapped host memory を試します。後続の pinned allocation や alias にも失敗する場合は、独立した VRAM fallback を試す実装経路があります。

## 実行時の詳細

環境値は `NativeEmbed::load()` のテーブル検証とサイズ計算の後に通常の `std::getenv()` で読みます。static cache はありません。ネイティブ pack のロード時にこの関数が一度評価され、ロード後の処理では環境値を再読せず、設定変更もロード済みテーブルの配置を変えません。ロード成功後は `set_native_embed()` で共有ポインターを設定し、layer の token embedding、verify、MTP/DFlash2 drafter などがそのテーブルを gather に使います。

要求した VRAM 配置に成功すると stderr に `strata: native embedding: STRATA_EMBED_VRAM=1: ... placed in VRAM ...` を出します。試行が条件不足または失敗なら `... STRATA_EMBED_VRAM=1 not taken (...): kept in mapped host memory` を出して通常の mapped 配置へ進みます。mapped pinned host allocation が失敗し、その代替 VRAM copy が成功した場合は `cannot pin ... kept in VRAM instead` を出します。配置ロードに失敗した場合、呼び出し元は `strata generate: <error>` を stderr に出して終了コード 1 を返します。生成開始後には、最終配置を `token embedding ... in VRAM` または `... in mapped host memory` と stderr に表示します。

## 根拠

- `src/core/native_head.cpp:124-149`: ネイティブ埋め込みの GGUF、tensor 形状・型・payload 検証とテーブルサイズ計算。
- `src/core/native_head.cpp:150-177`: 変数の読み取り、先頭文字判定、空き量の厳密な境界、確保・コピー、成功と未採用のログ。
- `src/core/native_head.cpp:178-229`: mapped pinned host memory の通常経路、確保・alias 失敗時の VRAM fallback とエラー。
- `src/program/generate.cpp:3087-3089,3848-3888,4424-4445`: `--native` と `--embd-gguf` の解析、native pack の場合のロード、ロード失敗時の終了、ロード後の配置ログ。
- `sycl/src/core/native_head.cpp:170-207,242-275` と `sycl/src/program/generate.cpp:2894-2913`: SYCL 実装は mapped host allocation を行うが `STRATA_EMBED_VRAM` を読まず、起動ログも mapped host memory としている。
- `src/core/layer.cpp:1322-1328`, `src/core/verify.cpp:1313-1315`, `src/core/mtp.cpp:936-946`: 設定済みのネイティブ埋め込みから token rows を gather する利用箇所。
- `docs/DETAILS.md:1535-1546`: CUDA opt-in prompt switch の表では `STRATA_EMBED_VRAM=1` を他の3スイッチと合わせた組として掲載し、その組の prompt 測定値を示している。個別スイッチ単独の性能値ではない。
