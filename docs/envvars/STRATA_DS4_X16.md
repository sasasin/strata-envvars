# `STRATA_DS4_X16`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver が独自に読む環境変数は対象外。

## 役割

HIP の DSV4.1 IQ register-weights kernel で、gate/up の入力を F32 行から読むか、呼び出し側が用意した F16 行から読むかを切り替えます。既定は F16 行を使う経路です。これは HIP 実装内の kernel 選択であり、他 backend の読み取りは確認できません。

## 値と判定

`runr<T, GU, BM, NW, NTW>()` の各 template 特殊化が初めて呼ばれた時に `static const bool` として評価されます。`getenv()` の文字列全体や数値は parse せず、値が存在し、かつ先頭文字が `'0'` の場合だけ無効にします（`src/dsv41/ds4_iq_hip_r.inc:218-221`）。

| 値 | `x16` 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（値は存在するが先頭文字は `\0`） |
| `0`、`0abc` | 無効 |
| `1`、`true`、`false`、空白で始まる値、その他 `0` 以外で始まる文字列 | 有効 |

大小文字、数値としての妥当性、後続文字は検査しません。

## 有効になる条件

この設定が影響するには、次の条件が必要です。

- HIP build であること。`ds4_iq_hip.inc` が `ds4_iq.cu` に含まれ、その HIP 実装に register-weights kernel が定義されています（`src/dsv41/ds4_iq.cu:1184`, `src/dsv41/ds4_iq_hip.inc:235`）。
- DSV4.1 IQ set が `launch_set()` に到達し、`hipk::launch()` が `ok_device()` を通ること。既定では gfx12 が対象、gfx11 は gfx1151 が既定対象で、その他 gfx11 は `STRATA_DS4_HIPK=1` の opt-in です。`STRATA_DS4_HIPK=0` は gfx12 を含めて無効化します（`src/dsv41/ds4_iq_hip.inc:237-270`; 呼び出し元 `src/dsv41/ds4_iq.cu:1185-1195`）。
- 対象 type が HIPK 対応で、`a.max_rows > 16`、次元・stride の条件を満たし、GU では `a.xf`、down では `a.xh` が検査上の 16-byte alignment を満たすこと（`src/dsv41/ds4_iq_hip.inc:296-304`）。`a.xf16` 自体はこの条件式で alignment 検査されません。条件を満たさなければ HIPK は採用されず、呼び出し元の通常 kernel に進みます。
- `STRATA_DS4_HIPK` の `atoi` 結果が `2` ではないこと。`2` は別の shared-memory weights kernel を選ぶため、この変数を読む `runr()` には入りません（`src/dsv41/ds4_iq_hip.inc:305-335`）。`HIPK_CFG` の選択も `runr()` の呼び出し先を決めます（同 `:307-329`）。

判定が有効でも、F16 入力が存在しない場合は F16 kernel を選ばず、通常の F32 入力 kernel を起動します。また down set では `GU` が false のため X16 経路になりません（`src/dsv41/ds4_iq_hip_r.inc:42-43,222-230`）。

## 実行時の詳細

`runr()` は gate/up (`GU == true`) の場合、`x16` が有効で `a.xf16 != nullptr` なら `set_kernel_r<..., true>` を起動します。それ以外は `set_kernel_r` の既定特殊化を起動します。前者の kernel は `a.xf16` の F16 行をロードし、後者は `a.xf` の F32 行をロードします（`src/dsv41/ds4_iq_hip_r.inc:42-63,222-230`）。`a.xf16` は呼び出し側の `sa.x16` から `iq::SetArgs::xf16` に渡されます（`src/dsv41/ds4_gguf.cu:1552-1566`）。

環境値の再評価は各 `runr` template 特殊化の初回呼び出し時だけです。その特殊化でキャッシュされた後にプロセス環境が変更されても、その特殊化の判定は変わりません。`runr()` 自体は複数の `T`, `GU`, tile parameter で呼ばれるため、単一のプロセス全体キャッシュとは限りません（`src/dsv41/ds4_iq_hip_r.inc:211-221`; 呼び出し先一覧 `src/dsv41/ds4_iq_hip.inc:309-329`）。

この変数専用のログや警告はありません。kernel launch が失敗すると `runr()` は `cudaPeekAtLastError() == cudaSuccess` を返し、false の場合 `launch_set()` は呼び出し元の通常 kernel 経路へ進みます（`src/dsv41/ds4_iq_hip_r.inc:224-231`, `src/dsv41/ds4_iq.cu:1185-1202`）。

## 根拠

- 変数の唯一の実参照・判定: `src/dsv41/ds4_iq_hip_r.inc:218-221`。リポジトリ全体の完全一致検索では、このほかに候補一覧と上記コメント以外の参照はありません。
- F16/F32 入力の選択と kernel 起動: `src/dsv41/ds4_iq_hip_r.inc:42-63,222-231`。
- HIPK の backend/device/shape 条件、`STRATA_DS4_HIPK`・`HIPK_CFG` による別経路: `src/dsv41/ds4_iq_hip.inc:237-270,286-335`。
- HIPK から通常 kernel への呼び出し経路と呼び出し側引数の引き渡し: `src/dsv41/ds4_iq.cu:1185-1202`, `src/dsv41/ds4_gguf.cu:1552-1566`。
