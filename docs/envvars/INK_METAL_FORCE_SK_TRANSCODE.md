# `INK_METAL_FORCE_SK_TRANSCODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal backend のモデルファイルローダーで、GGUF の expert が Metal に対応する native GGUF kernel を使える場合でも、native GGUF 格納を選ばず S_K 形式への transcode 経路を選ばせます。Strata 形式の通常ロードや、Metal 以外の backend を制御する変数ではありません。読み取りは `InkMetalModel::load_from_model_file` 内で行われます。`engine/src/inkling2/metal/ink_metal_common.h:572-576,651-682`

## 値と判定

`std::getenv` の戻り値が非 null かつ、その先頭バイトが文字 `'1'` かだけを調べます。文字列全体の比較や数値変換はしません。したがって未設定と空文字は false、先頭が `1` の文字列（`1`、`10`、`1anything`、`1 `）は true です。`0`、`true`、` 1`、`01`、`True` は false です。大文字小文字や後続文字は判定に影響せず、数値妥当性・範囲の検査もありません。`engine/src/inkling2/metal/ink_metal_common.h:656`

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `INK_METAL_WITH_MODEL_FILE` を使う Metal backend の model-file loader | false（native 条件を満たす GGUF expert は native 候補） | 先頭文字が `1` | 空文字、`0`、`true`、先頭が空白の ` 1` など |

## 有効になる条件

- `MetalInkBackend::init` が `load_from_model_file` を呼ぶ経路であることが必要です。`model.kind == Strata` かつ `INK_METAL_FORCE_MODEL_FILE` の先頭が `1` ではない場合、backend は `mod_.load(...)` を使うため、この変数は評価されません。Strata 以外のモデルは model-file loader に入ります。`engine/src/inkling2/metal/ink_metal_backend.mm:92-103`
- 機能が native GGUF 選択を変えるのは、モデルが `Gguf` で `gguf_adapter` があり、expert の両方の code ID が `FMT_GGUF_RAW`、対応する層が存在し、両方の型に Metal kernel がある場合です。この条件を満たさない expert は、変数が false でも native 経路に入りません。`engine/src/inkling2/metal/ink_metal_common.h:673-682`
- この変数が true だと、上記条件を満たしていた expert も `native_ok` にならず、計画済みの `adj_dir` と `read_or_transcode_expert` を使います。`engine/src/inkling2/metal/ink_metal_common.h:656-659,673-684,721-745`
- `INK_METAL_FORCE_MODEL_FILE` は model-file loader に入るかどうかを左右する別変数です。CLI 引数がこの変数の判定を上書きする処理は、確認した呼び出し経路にはありません。`engine/src/inkling2/metal/ink_metal_backend.mm:98-103`
- `INK_METAL_WITH_MODEL_FILE` は `ink_metal_backend.mm` で定義され、そのファイルが共通ヘッダーを取り込みます。CMake の Metal backend ターゲットに含まれる実装です。`engine/src/inkling2/metal/ink_metal_backend.mm:14-15`; `engine/src/inkling2/metal/CMakeLists.txt:27-30,50-51`

## 実行時の詳細

`load_from_model_file` が Section 1 を読み込んだ後、expert directory を計画する前に評価し、結果を関数内の `const bool force_sk` に保持します。この呼び出し内の expert 計画で使われ、別の static cache はありません。モデル初期化時に loader が再度呼ばれれば再評価されます。値をモデルロード後に変更しても、既に決めた expert 配置や変換には反映されません。読み取り式では `getenv` を最大 2 回呼びます。`engine/src/inkling2/metal/ink_metal_common.h:651-659,673-684`

transcode planner は GGUF_RAW の expert に対し、GGML 型から S_K code と格納サイズを計画します。native 経路が選ばれなかった expert は並列読み込み時に `read_or_transcode_expert` へ渡され、GGUF_RAW なら実データを S_K へ変換し、既に非 GGUF_RAW ならその expert body を読み出して既存 code のまま返します。したがって、この変数は全モデルを無条件に変換する指定ではなく、条件を満たす native GGUF expert を native のまま使う選択を抑止します。`engine/src/inkling2/ink_gguf_transcode.h:373-399,402-447`; `engine/src/inkling2/metal/ink_metal_common.h:721-745`

## ログと測定値

この変数専用の有効・無効ログや警告はありません。model-file loader の成功ログは stderr に `[ink_metal] loaded %s (src=%s, build=%s, %.2f GiB arena, trunk=%zu, dspark=%zu, experts=%zu, native_gguf=%zu, sec4_bufs=%zu) in %.2fs (workSet=%.1f GiB, maxBuf=%.1f GiB)` を出します。`native_gguf` は native として保持した expert 数なので、該当する GGUF と Metal kernel の条件下ではこの変数の効果が数値に現れます。読み込み・transcode の失敗時は loader が false を返し、`MetalInkBackend::init` も false を返します。失敗理由は `err` に設定される経路がありますが、この箇所に一律の失敗ログ出力はありません。`engine/src/inkling2/metal/ink_metal_common.h:706-710,721-745,754-762`; `engine/src/inkling2/metal/ink_metal_backend.mm:98-103`

性能・正確性の測定値は、確認した該当ソースおよび `docs/DETAILS.md` に記載を確認できません。

## 根拠

- 読み取りと判定: `engine/src/inkling2/metal/ink_metal_common.h:651-659`
- native GGUF 可否と選択結果: `engine/src/inkling2/metal/ink_metal_common.h:673-693`
- transcode 計画・読み出し・変換: `engine/src/inkling2/ink_gguf_transcode.h:373-399,402-447`
- model-file loader の呼び分け: `engine/src/inkling2/metal/ink_metal_backend.mm:92-103`
- loader の成功ログ・失敗伝播: `engine/src/inkling2/metal/ink_metal_common.h:706-710,721-762`; `engine/src/inkling2/metal/ink_metal_backend.mm:98-103`
