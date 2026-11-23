# `--model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL） |
| オプション | `--model` |
| 別名 | `--native`、`-m` |
| 値 | モデルファイルのパス（値は次の argv 要素から文字列として取得） |

## 役割

SYCL 版 Inkling-2 エンジンが扱うモデルファイルのパスを指定します。通常経路では `.strata` ファイルを読み込み、マニフェストと重みを解析して SYCL デバイス上などにモデルをロードします。`--info` と併用すると同じパスを使って情報だけを調べ、モデル実行の初期化をせず終了します。

## 使い方

```sh
# モデルをロードして通常の初期化・実行経路へ進む
strata-inkling-sycl --model ./model.strata

# ファイルをロードせず、モデル情報を表示する
strata-inkling-sycl --model ./model.strata --info
```

## 値と既定値

- `--model`、`-m`、`--native` は同じ分岐で処理され、後続の引数を `model_path` に代入します。値の形式・拡張子・存在確認を parser 自体では検査しません。ファイル形式の確認は後段の読み込み処理で行われます（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-118`、`engine/src/inkling2/sycl/ink_sy_common.h:660-683`）。
- 省略時の `model_path` は空文字列です。空文字列のまま処理が進むと usage を stderr に出し、終了コード `1` で終了します（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-104,166-169`）。
- 値を伴わない末尾の `--model` も空文字列になります。parser は次の引数がオプションかどうかを判定せず、存在すればそれを値として消費します（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-116`）。
- `--model` を複数回指定した場合は、走査中に同じ変数へ代入するため最後の指定値が残ります。`--info <path>` は `--model` を省略した場合にもパスを設定し、併用時は argv 上で後に処理された代入が残ります（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-119`）。

## 実行時の動作

`--info` が指定されている場合、`probe_only` はパスを `rb` で開き、4096 byte のヘッダーと Section 0 のマニフェストを読み取ります。マニフェストを解析した後、標準出力にバージョンとモデル情報を出して終了します。この経路は全重みのロードや runner 初期化へ進みません（`engine/src/inkling2/sycl/ink_sy_main.cpp:171-180`、`engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`）。

`--info` がない場合は `InkSyModel::load` にパスを渡します。処理はファイルを開き、4096 byte ヘッダー、Strata magic、Section 0 マニフェストを読み、モデル設定を解析した後、tensor と expert データを読み込んでデバイス用領域などへ配置します。ロード成功時はモデル名・build・デバイス・ロード時間等を stderr に出力します（`engine/src/inkling2/sycl/ink_sy_main.cpp:183`、`engine/src/inkling2/sycl/ink_sy_common.h:660-683,685-716,739-770,956-989`）。

## 適用条件と副作用

- この文書の対象は `strata-inkling-sycl` の SYCL parser です。CUDA/HIP と Metal 版は別の parser scope です（`docs/cli/000_cli_tools.md:12`、`docs/cli/README.md:1572-1583`）。
- 通常経路ではモデルファイルを読み取り、モデル tensor/expert データに応じたホスト・デバイスメモリ確保と SYCL 転送を伴います。`--info` 経路ではファイルを開いてヘッダーとマニフェストを読む範囲にとどまります（`engine/src/inkling2/sycl/ink_sy_common.h:660-683,685-716,1385-1397`）。
- `.strata` 拡張子の強制や、ファイルパスの事前検証は確認できません。通常ロードでは Strata magic（`STRATA\0\1`）とマニフェストを検査します（`engine/src/inkling2/sycl/ink_sy_common.h:664-683`）。
- 関連する GPU 選択や expert 配置の引数は、この `--model` 文書の対象外です。それらの値は loader に別引数として渡されます（`engine/src/inkling2/sycl/ink_sy_main.cpp:183`）。

## 出力とエラー

- パスが空なら usage を stderr に出し、終了コード `1`（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169`）。
- ファイルを開けない、ヘッダーが短い、magic が不正、Section 0 やマニフェストの読み取り・解析に失敗した場合、`--info` では `[ERROR] <理由>` を stderr に出して終了コード `1`（`engine/src/inkling2/sycl/ink_sy_main.cpp:173-175`、`engine/src/inkling2/sycl/ink_sy_common.h:1385-1397`）。通常ロードも loader が返すエラーを `[ERROR] <理由>` として stderr に出し終了コード `1`（`engine/src/inkling2/sycl/ink_sy_main.cpp:183`）。
- 通常ロード成功時のロード統計は stderr、`--info` 成功時のバージョン・マニフェスト情報は stdout に出力されます（`engine/src/inkling2/sycl/ink_sy_common.h:971-987`、`engine/src/inkling2/sycl/ink_sy_main.cpp:175-180`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-119` — CLI 初期値、引数走査、`--model` と別名、`--info` によるパス設定。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-183` — 空パス時の usage、情報表示経路と通常ロード経路。
- `engine/src/inkling2/sycl/ink_sy_common.h:469-499,502-588` — Section 0 読み取り・展開と Inkling マニフェスト解析。
- `engine/src/inkling2/sycl/ink_sy_common.h:660-683,685-716,739-770,956-989` — 通常ロードの入力検査、tensor/expert 読み込み・配置、成功時出力。
- `engine/src/inkling2/sycl/ink_sy_common.h:1385-1397` — `--info` 用のファイル・マニフェスト probe。
