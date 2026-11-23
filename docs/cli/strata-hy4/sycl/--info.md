# `strata-hy4-sycl --info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--info` |
| 別名 | なし |
| 値 | 任意の `.strata` ファイルパスを1つ。次の引数が `-` で始まる場合はファイルパスとして取り込まない |

## 役割

SYCL 版 Hy4-Flash エンジンの情報、または指定した `.strata` ファイルの manifest 情報を、`key=value` 形式で標準出力へ表示して終了します。ソース内の実装は GPU を使わない情報表示として設けられており、ファイルを渡すと Vision shard と通常モデルを区別します（`engine/src/hy4flash/sycl/sy_main.cpp:44-67`）。

## 使い方

```sh
# エンジンの機能情報を表示
strata-hy4-sycl --info

# モデルまたは Vision shard の manifest 情報を表示
strata-hy4-sycl --info ./model.strata
```

## 値と既定値

- ファイル引数は省略できます。省略時は `arch=hy4flash`、`backend=sycl`、drafter / speculative decoding 関連フラグ、`images=1`、ビルド時の `HY4_VERSION` を含む1行を出力して成功終了します（`engine/src/hy4flash/sycl/sy_main.cpp:14-16,45-49`）。
- `--info` の直後に次の引数があり、その先頭文字が `-` でなければ、その1引数をファイルとして読みます。`--info` はその場で処理を終えるため、後続のオプションは処理されません。値の追加検証や別名はありません（`engine/src/hy4flash/sycl/sy_main.cpp:121-124`）。
- ファイル指定時、まず `vision_probe` で Vision shard として開き、検査に通れば `arch=hy4flash_vision backend=sycl images=1 tensors=<件数>` を出力します（`engine/src/hy4flash/sycl/sy_main.cpp:50-55`）。Vision shard と判定されなければ `StrataFileReader` で開き、manifest から層数・hidden size・語彙数・expert 数・EOS ID・drafter 有無を出力します（`engine/src/hy4flash/sycl/sy_main.cpp:56-66`）。

## 実行時の動作

`main` は引数解析より先に、`UR_LOADER_USE_LEVEL_ZERO_V2` が未設定ならプロセス内で `0` を設定し、`ONEAPI_DEVICE_SELECTOR` が未設定なら `HY4S_BACKEND=opencl` の場合に `opencl:gpu`、それ以外に `level_zero:gpu` を設定します。明示された `ONEAPI_DEVICE_SELECTOR` は保持されます（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`）。したがって `--info` もこの初期化を通りますが、情報表示処理自体は SYCL デバイスの問い合わせやモデル推論を呼び出しません（`engine/src/hy4flash/sycl/sy_main.cpp:45-67,121-124`）。この環境変更は当該プロセス内です。

通常モデルの drafter 表示は、manifest tensor map に所定の2 tensor が両方ある場合だけ `dfly2`、それ以外は `none` です（`engine/src/hy4flash/sycl/sy_serve.h:231-233`）。なお、通常モデル出力の `images` は実装上 `1` を固定で出力します。一方、serve 起動時の `images` は Vision shard の検査結果で決まります（`engine/src/hy4flash/sycl/sy_main.cpp:64-65`; `engine/src/hy4flash/sycl/sy_serve.h:313-332`）。

## 適用条件と副作用

- 対象は SYCL 版 `strata-hy4-sycl` です。オプション分岐はモデル読込・serve 起動の分岐より前にあり、`--info` を指定すると情報出力後すぐ戻ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-124`）。
- `.strata` の内容確認ではファイルを読みますが、GPU を初期化せず、ファイルを書き換える処理もありません（`engine/src/hy4flash/sycl/sy_main.cpp:45-67`; `engine/src/hy4flash/run/hy4_vision.h:67-124`）。
- 起動時の環境変数設定は、上記のとおり未設定時にプロセス内で行われます（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`）。

## 出力とエラー

- 成功時は `printf` による1行を標準出力へ出し、戻り値 `0` です（`engine/src/hy4flash/sycl/sy_main.cpp:45-66`）。
- 指定ファイルを通常モデルとして開けない場合、`open: <reader error>` を標準エラーへ出し、戻り値 `1` です（`engine/src/hy4flash/sycl/sy_main.cpp:56-61`）。Vision shard 判定の失敗自体は表示せず、通常モデルとしての読込みへ進みます（`engine/src/hy4flash/sycl/sy_main.cpp:50-58`）。
- 通常モデルの JSON manifest 解析には `parse_manifest` を呼びますが、この `--info` 分岐内には例外を整形する catch がありません（`engine/src/hy4flash/sycl/sy_main.cpp:62-65`; `engine/src/hy4flash/run/hy4_manifest.h:78-80`）。不正 manifest 時の具体的な標準エラー文や終了コードはこの分岐だけからは確定できません。

## 根拠

- `docs/cli/README.md:1447-1477` — `strata-hy4-sycl` の scope と `--info` の索引リンク。
- `engine/src/hy4flash/sycl/sy_main.cpp:44-67,79-92,105-124` — 情報出力、値の受け取り、早期終了、起動時初期化。
- `engine/src/hy4flash/run/hy4_vision.h:67-124` — Vision shard の読込み・manifest 検査。
- `engine/src/hy4flash/run/hy4_manifest.h:78-80` — 通常モデル manifest の解析入口。
- `engine/src/hy4flash/sycl/sy_serve.h:231-233,313-332` — drafter 判定と serve 時の images 判定。
- `engine/src/artifact/strata_reader.cpp:33-59` — `.strata` ファイルの open とヘッダー検証。
