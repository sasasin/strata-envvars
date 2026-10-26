# `DS4_COMMIT_CAP_GB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1（DS4）CUDA 実装の GPU expert 配置で使う「残り commit 容量」に上限を設け、同時に GPU の割り当てを commit 制約対象として扱わせます。ソースコメントではテスト用とされています。通常の Windows UMA 判定を置き換えるのではなく、この変数が設定されていると全デバイスが commit 制約対象になります。その結果、GPU に置く expert 数や、CPU lane の expert を RAM にコピーできる量にも影響します。

## 値と判定

`DS4_COMMIT_CAP_GB` は `std::getenv` で設定有無を調べ、容量値は `std::atof` で読みます。文字列全体の検証やエラー処理はありません。

| 値 | 処理 |
|---|---|
| 未設定 | 上限を適用しない。Windows では統合 GPU の属性により commit 制約対象かを判定する。 |
| 数値文字列 | 先頭から `atof` が変換できる数値に `1e9` を掛けた値（10進 GB）を、OS が報告した残り commit 容量との小さい方にする。例: `12` は 12,000,000,000 byte。 |
| 空文字、数値に変換できない文字列 | `atof` の結果は 0 となり、容量上限は 0 byte。変数が設定済みであるため全デバイスを commit 制約対象にもする。 |
| 数値の後ろに余分な文字がある値 | `atof` が先頭の数値部分を変換し、後続部分は検証しない。 |
| 負の数 | 上限計算の結果は最終的に 0 byte に clamp される。 |

未設定時の既定値は OS の commit 情報です。Windows 以外では `os::commit()` の各値は sentinel（`~uint64_t{0}`）のままで、変数未設定なら commit 上限を設けません。明示設定時は commit 情報の有無にかかわらず `atof(value) * 1e9` が上限に使われます。commit 余裕から差し引く margin は `max(8 GiB, RAM の 10%)` です（RAM が不明なら 8 GiB）。差し引き後は 0 未満になりません。

## 有効になる条件

- 参照箇所は `src/dsv41/ds4_model.cu` の DS4 CUDA engine です。DS4 以外の実行経路への適用は確認できません。
- 変数を設定すると、OS や GPU 属性によらず `commit_charged()` は true を返します。未設定時は Windows のみ `cudaDevAttrIntegrated` を問い合わせ、統合 GPU なら true、取得失敗または非統合 GPU なら false です。Windows 以外で未設定なら false です。
- GPU expert 配置では commit 制約対象のデバイスに対して commit room を使い、各 GPU group の expert budget をさらに制限します。値を小さくすると GPU に載る expert が減り、CPU 側に残る expert が増える場合があります。
- `commit_room()` は RAM コピー可否の計算にも呼ばれます。そのため設定値は `DS4_COPY_GB` を使った expert コピーなどの上限にも作用します。
- 設定有無によって `DS4_UMA_GPU_RESERVE_GB` の適用経路にも入ります。設定時は commit 対象として扱われるデバイスで、GPU の後続バッファ用に既定 `4 GiB + context に応じた量` を expert budget から予約します。`DS4_UMA_GPU_RESERVE_GB` が設定されている場合は、その値を `atof` で読み GiB 単位で予約量を置き換えます。

## 実行時の詳細

値を static cache するコードはありません。`commit_room()` は呼ばれるたびに環境変数を読み直し、`commit_charged()` も各デバイス判定時に設定有無を確認します。主な呼び出しは、モデル初期化時の `place_experts()`、CPU lane の RAM 適合判定、expert コピー予算の計算です。プロセス実行中に環境を書き換える操作はこのコードにはありません。

commit 制約で GPU に置けなかった expert がある場合、初期化時に stderr へ `ds4: WARNING: ...` を出し、Windows の commit と page file についての説明と必要 page file 容量を示します。server の情報行には `NOTE experts: ...` と `INFO gpu_commit_capped_gb=... pagefile_hint_gb=...` が追加されます。制約対象で expert が残らず、verbose が有効な場合は commit room の情報行が stderr に出ます。

## 根拠

- 値の読み取り、10進 GB 変換、margin、OS ごとの commit 情報: `src/dsv41/ds4_model.cu:1081-1106`, `src/dsv41/ds4_os.hpp:541-559`。
- GPU デバイスが commit 制約対象となる条件と、GPU budget への適用、UMA 予約: `src/dsv41/ds4_model.cu:3896-3937`。
- 配置制限時の stderr 警告: `src/dsv41/ds4_model.cu:3971-3985`。
- RAM コピー予算への適用: `src/dsv41/ds4_model.cu:4271-4279`。
- server 情報行: `src/dsv41/ds4_model.cu:9308-9326`。
- `docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。関連する一般説明として、`docs/UNSLOTH_Q4.md:145-154` は Windows で RAM とは別に commit 容量が expert budget を制限しうることを説明していますが、`DS4_COMMIT_CAP_GB` 自体の仕様説明ではありません。
