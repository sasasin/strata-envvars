# `STRATA_HIP_PROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2 の HIP backend で、HIP Graph の利用を制限し、通常バッチ処理中の層別 GPU 時間計測を有効にする診断用設定です。値が `2` 以上だと Graph を使わず計測を有効にします。値 `1` は Graph 適格性を変えず、Graph を使わない場合に限って大きいバッチの計測を有効にします。計測時間は stderr に出ます。読み取りと分岐は `HipBackend::forward_batch` にあります（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1514,3241-3245,3341-3358`）。

## 値と判定

各 `forward_batch` 呼び出しで `std::getenv` により設定の有無を調べ、設定されていれば値を `std::atoi` に渡します。未設定は `0`。空文字も `atoi` が数値変換できず `0` になります。文字列全体の検証、末尾の検査、範囲制限はありません。`atoi` は先頭の空白と符号の後の10進数字列を変換し、数字列の後ろは判定に使いません。そのため `2abc` は `2`、`0anything` は `0`、`true` / `false` / 空文字 / 数字で始まらない文字列は `0` として扱われます。真偽語としての大文字小文字の扱いはありません。

| HIP backend の実行時 | unset | 計測・Graph 判定 | 例として無効（計測を有効化しない） |
|---|---:|---|---|
| `atoi` の結果 `< 2`（例: `0`, `1`, 負数） | `0` | Graph は他の適格条件で判定。`1` かつ Graph 不使用かつ `B >= 64` のときだけ層別計測 | `0`, `-1`, `true`, `0anything` は計測を有効化しない |
| `atoi` の結果 `>= 2`（例: `2`, `3`, `2abc`） | — | Graph を無効化し、層別計測を有効化 | 該当なし（整数値に上限・範囲検査なし） |

`atoi` は変換結果の妥当性を別途検査せず、数値部分の後続文字を拒否しません。したがって文字列が `1` に変換されるかどうかと計測の実効条件は別です（同ファイル `:3241-3244,3341`）。

## 有効になる条件

- `STRATA_ENABLE_HIP` で Inkling-2 HIP backend がビルドされ、その backend の `forward_batch` が実行される必要があります。Inkling-2 はこの CMake 条件で HIP サブディレクトリを追加し、HIP ターゲットを構成します（`engine/CMakeLists.txt:104,149-151`; `engine/src/inkling2/CMakeLists.txt:200-202`; `engine/src/inkling2/hip/CMakeLists.txt:74-82,96-116`）。CUDA、Metal、SYCL、CPU 側の同名設定を読むコードは見つかりませんでした。
- 変換値が `2` 以上なら、通常の `forward_batch` で Graph が抑止され、バッチサイズにかかわらず計測が有効です（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3241-3244,3341`）。
- 変換値が `1` のときは `B >= 64` で、かつ Graph が選ばれない場合だけ計測します。Graph の適格条件は、全層が GPU 常駐、全バッチ要素が logits を要求、画像行なし、`taps_out == nullptr`、および distinct slot の `B <= 64` または非 distinct slot の指定された `rec_slot` / group / `B` 条件です。適格なら `prof_mode == 1` でも Graph が使われ、層別計測は行われません（同ファイル `:3230-3245,3341`）。
- 値 `0` 相当や負数では計測しませんが、その他の Graph 条件を満たせば Graph は利用できます（同ファイル `:3241-3245,3341`）。
- この backend の別機能である tree verify は `STRATA_HIP_TREE_PROF` を参照しており、この変数の `prof_mode` は参照しません（同ファイル `:4690-4706`）。

CLI 引数や設定ファイルによる上書きは、この読み取り経路では見つかりませんでした。他の環境変数との優先順位もありません。

## 実行時の詳細

値は `HipBackend::forward_batch` の各呼び出し中、Graph の適格性判定前にローカル変数 `prof_mode` として読み取られます。関数内 static やプロセス起動時の cache はありません。したがって、環境の値がプロセス内で変更された場合、後続の `forward_batch` 呼び出しで再評価されます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1514,3241-3245`）。

`prof_on` が真なら HIP event を11個作成し、各層の区間に event を記録します。各層の終端で event 8 の同期と8区間の経過時間取得を行って累積し、バッチの stream 同期後に合計と unembed 時間を報告します。値 `2` 以上ではこの計測経路に入るため HIP Graph の capture/replay を使いません。一方、計測が無効でも Graph 条件を満たせば Graph を使えます（同ファイル `:3341-3358,3360-3363,4420-4426,4470-4509,4556-4569`）。

この値は計測のために実行経路（Graph の有無）と event 記録・同期を変えます。読み取り値をモデルの logits や token 選択値に渡す処理はありません（同ファイル `:3241-3245,3341-3358,4531-4556`）。

## ログと測定値

計測が有効な場合、`forward_batch` の stream 同期後に次の形式を stderr に出します。`B`、合計ミリ秒、unembed ミリ秒、合計 tok/s と8区間のミリ秒値を含みます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4556-4567`）。

```text
[HIP-PROF] B=%d sum=%.2fms unemb=%.2fms tot=%.2fms (%.1f tok/s) | res_ctrl=%.2f qkvrg=%.2f sconv_kv=%.2f attn=%.2f wo_post=%.2f moe_prep=%.2f moe_w13=%.2f moe_w2_post=%.2f
```

計測区間に入らない場合、この行は出ません。`hipEventCreate` / event 記録 / 経過時間取得の戻り値は無視されます。stream 同期に失敗した場合も、同期結果を `ok` に保存した後に計測ログ処理を行い、最終的な戻り値は同期結果に従います（同ファイル `:3344-3358,4556-4569`）。Strata の `docs/DETAILS.md` および `docs/SETTINGS.md` に、この変数についての計測値や説明は見つかりませんでした。

## 根拠

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1514,3241-3245,3341-3358,4420-4426,4470-4509,4556-4569,4690-4706` — 読み取り、Graph と計測条件、event 計測とログ、tree verify 側の別変数。
- `engine/CMakeLists.txt:104,149-151`; `engine/src/inkling2/CMakeLists.txt:200-202`; `engine/src/inkling2/hip/CMakeLists.txt:74-82,96-116` — HIP backend のビルド条件。
