# `DS4_COPY_PIN_RO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

DS4 の CPU lane 用に RAM へコピーされた expert 領域を pin する際、CUDA host registration に read-only フラグを使うかを選びます。この変数だけでは pin を開始しません。pin が有効になったときだけ値が読まれ、非ゼロなら `cudaHostRegisterReadOnly`、ゼロなら `cudaHostRegisterPortable` を使います。pin された領域は prompt の flow 経路で RAM 上の位置から GPU へ DMA されます（`src/dsv41/ds4_model.cu:5131-5158,3812-3827`）。

## 値と判定

値は `std::getenv` で設定有無を確認し、設定されていれば `std::atoi(...) != 0` で判定します。文字列全体の検証やエラー報告はありません。

| 値 | `ro` の判定 | 登録フラグ |
|---|---:|---|
| 未設定 | false | `cudaHostRegisterPortable` |
| 空文字 | false（`atoi` が 0） | `cudaHostRegisterPortable` |
| 先頭の数値部分が 0、または数値に変換できない文字列（例: `0`, `false`） | false | `cudaHostRegisterPortable` |
| 先頭の数値部分が非ゼロ（例: `1`, `-1`, `2`, `1tail`） | true | `cudaHostRegisterReadOnly` |

`atoi` は整数として読める先頭部分で判定するため、後続の文字列は判定に含まれません。CLI 引数によるこのフラグの上書きはありません。別変数 `DS4_COPY_PIN` は pin 自体の有効・無効を決めるため、pin が無効なら本変数の値は参照されず効果もありません（`src/dsv41/ds4_model.cu:98-101,5144-5152`）。

## 有効になる条件

`copy_experts()` がコピー予算を持ち、pin 判定まで進むことが必要です。実際に登録対象の RAM chunk があれば次の規則で pin を選びます。

- GGUF の CPU lane expert を RAM にコピーし、実際の RAM chunk が確保されていること（`src/dsv41/ds4_model.cu:4877-4880,4959-4965,5062-5066`）。
- `DS4_COPY_PIN` が明示されていれば、その `atoi` 判定が非ゼロであること。未設定時は `copy_pin_default()` の既定規則が使われ、旧 defaults (`defaults_026()`) では OFF。それ以外は、全コピー領域が huge-page arena にあるか、RDNA4 で GPU expert share が 0.5 以上であり、かつ RAM chunk がある場合に ON です（`src/dsv41/ds4_model.cu:5144-5145`; `src/dsv41/ds4_experts_rule.hpp:174-180`）。

明示的な `DS4_COPY_PIN` が非ゼロなら `copy_pin_default()` は chunk の有無にかかわらず true を返します。コピー予算はあるが全 chunk 確保に失敗した場合も `DS4_COPY_PIN_RO` は読まれますが、登録ループは 0 回で、prompt の RAM 直結経路に使える領域はありません（`src/dsv41/ds4_model.cu:5062-5072,5144-5158`; `src/dsv41/ds4_experts_rule.hpp:176-179`）。

したがって `DS4_COPY_PIN_RO=1` だけを指定しても pin は有効になりません。コードにはこの変数専用の OS 判定や CLI 分岐はなく、登録には `cudaHostRegister` を呼びます。HIP compatibility header では `cudaHostRegisterReadOnly` を `hipHostRegisterReadOnly` に対応付けています（`include/strata/platform/hip_compat/strata_hip.h:61`; `include/strata/hip_compat/cuda_runtime.h:80`）。

## 実行時の詳細

読み取りは `copy_experts()` の expert コピー完了後、`pin_copies` が true の場合に行われます。値は static cache されず、この処理に到達するたび評価されます。各 RAM chunk を順番に登録し、すべて成功すれば `ram_pinned` が true になります。最初の登録失敗で残りの chunk 登録を止め、stderr に `ds4: pinning the copied experts failed: the prompt path stages them` を出します。全登録成功時は `%s` 部分が `read-only` または `read-write` になる完了ログを出します（`src/dsv41/ds4_model.cu:5146-5159`）。

登録成功時、prompt flow は RAM 上の expert を staging に複製せず、元の領域を DMA 元として指定します。登録されていない場合はこの直結経路を使わず、通常の staging 処理へ進みます（`src/dsv41/ds4_model.cu:3812-3832`）。Model の破棄時には `ram_pinned` が true の場合に各 chunk を unregister します（`src/dsv41/ds4_model.cu:1507-1509`）。この変数自体に専用の警告・終了経路はありません。登録失敗も `copy_experts()` の失敗にはせず、prompt の staging 経路へ続きます。

## 根拠

- 全参照の検索では `src/dsv41/ds4_model.cu:5139` の説明コメントと `:5147` の実読み取りのみ。共通 helper や動的な名前渡しによる別読み取りは確認されませんでした。
- 値の読み取りと登録フラグ選択: `src/dsv41/ds4_model.cu:5144-5152`。
- pin の既定条件と明示指定の優先: `src/dsv41/ds4_experts_rule.hpp:174-180`。
- prompt flow の DMA 元切替: `src/dsv41/ds4_model.cu:3812-3832`。
- `docs/DETAILS.md` と関連設計資料には、この read-only 切替についての追加説明・測定値を確認できませんでした。
