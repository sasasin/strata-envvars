# `STRATA_KV_ROT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

`--kv int8` で保存する Key / Value に Hadamard 回転を適用する opt-in の設定です。回転後の K/V を保存し、attention で使う query にも回転を適用して内積を保ちます。attention 出力は逆変換（Hadamard 変換は自己逆）して後続計算へ渡します。INT8 K/V 以外では、この変数で実際の回転は有効になりません。

## 値と判定

CUDA/HIP 用 `src/program/generate.cpp` と SYCL 用 `sycl/src/program/generate.cpp` は同じ判定です。環境変数の文字列全体や数値としての妥当性は調べず、値が存在し、先頭文字が `'1'` かだけを確認します。

| 値 | 回転フラグ |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭が `1`（例: `1`, `10`, `1abc`） | ON |
| その他（例: `0`, `true`, ` 1`） | OFF |

## 有効になる条件

- 実際に K/V の保存と attention が回転するのは `--kv int8` の場合です。状態初期化では `kv_rot = kv_q4 || (kv_int8 && g_kv_int8_rot)` と設定されます。
- `--kv q4_0` は Hadamard 回転を常時使う形式なので、この環境変数には依存しません。
- `--kv fp16` では環境変数が ON でも `kv_rot` は立ちません。
- `--kv k8v4` の main-layer state は hybrid として初期化され、`kv_int8` が false になります。この main-layer の K8V4 固有の経路（K は INT8、V は回転 Q4_0）は `STRATA_KV_ROT` で切り替わりません。一方、MTP drafter を使う場合、その draft state は K8V4 ではなく INT8 で作られるため、この環境変数が ON なら draft K/V の回転には適用されます。

## 実行時の詳細

生成引数の検証後、`--kv` を内部形式に正規化してから `STRATA_KV_ROT` を読み、回転フラグをグローバル設定します。値が ON かつ `--kv int8` の場合だけ、stderr に次の行を出します（それ以外はこの変数によるログはありません）。

```text
strata generate: STRATA_KV_ROT=1: INT8 K/V through the Hadamard rotation (opt-in)
```

状態初期化で INT8 K/V かつ回転 ON なら、prompt prefill では K/V を回転してから保存し、query にも回転をかけます。decode / verify でも K/V を回転して保存し、attention query を回転してから参照します。attention の出力は回転を戻してから後続処理に渡します。これらは CUDA/HIP 実装と SYCL 実装にあります。

会話セッションを保存・復元する経路では、この環境変数を `SessionConfig.kv_rot` に再度読み込んで設定指紋に含めます。そのため `STRATA_KV_ROT` の ON/OFF を変えると、他の設定が同じでも保存済み会話の設定指紋が変わります。回転 INT8 と非回転 INT8 では保存された K/V の意味が異なるため、snapshot の形式識別値にも回転用の差分が付きます。

フラグ設定は `--kv` の初期処理時に読み取られ、各状態の `kv_rot` は状態初期化時に決まります。設定指紋の生成では環境をもう一度読み取ります。したがって通常の起動方法では起動前に値を設定してください。プロセス中に環境を変更した場合の再初期化や同期は実装されていません。

実装コメントは NVFP4 pack での first-token KL が `0.0066 -> 0.0051`、IQ2_XS で `0.0022 -> 0.0054` だったと記していますが、同コメントに比較条件・測定方法の詳細はありません。この値から品質や速度の一般的な効果は結論できません。

## 根拠

- 値の読み取り、`--kv` 正規化、回転設定、条件付きログ: `src/program/generate.cpp:2448-2461`。SYCL 側も同じ: `sycl/src/program/generate.cpp:2249-2262`。
- フラグの格納と状態への適用条件、K8V4 の除外: `src/core/layer.cpp:178-184,689-705`。
- decode で query 回転・K/V format 別 gather・attention 出力の逆回転: `src/core/layer.cpp:1133-1164`。
- prefill での K/V 保存前および query の回転: `src/prefill/prefill.cpp:2690-2710`。SYCL/CUDA 共通の device verify と MTP でも `kv_rot` に基づく処理がある: `src/core/verify.cpp:1245-1253`, `src/core/mtp.cpp:332-352,755-758,822-826`。
- 会話設定での再読込と fingerprint への格納: `src/program/generate.cpp:7783-7789`, `src/core/conversation_file.cpp:878-887`。設定指紋の対象に `STRATA_KV_ROT` を含める説明: `docs/DETAILS.md:1162-1175`。
- snapshot の回転識別: `src/core/conversation_snapshot.cpp:48-53`。
- `--kv q4_0` の回転と INT8 rotation の opt-in 注記、およびコメント中の KL 値: `include/strata/core/layer.hpp:309-318`, `src/program/generate.cpp:2453-2460`。
