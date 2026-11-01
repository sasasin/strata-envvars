# `--replica-profile`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（POSIX: `./setup.sh`、Windows: `START-HERE.bat`） |
| オプション | `--replica-profile` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False` |

## 役割

複数 GPU のセットアップで、対応する Qwen3.8 モデルと十分な RAM がある場合に、GPU ごとに独立 engine を置く serving profile を opt-in します。通常の一つの layer split の代わりに複数 replica を設定し、RAM 上の expert arena を共有できる環境では共有を有効にします。これは setup の選択を行うフラグで、単独でサーバーを直接起動するオプションではありません（`setup.py:9195-9203, 10338-10360`; `strata_control/replica_profile.py:1-20, 101-130`）。

## 使い方

Linux で2枚の GPU を指定して再セットアップし、セットアップ後の自動起動を避ける例です。Windows では `START-HERE.bat --setup --replica-profile --gpus 0,1 --no-start` として同じ parser に渡せます。

```sh
./setup.sh --setup --replica-profile --gpus 0,1 --no-start
```

`--gpus` は対象 GPU の選択、`--no-start` はセットアップ後のモデル起動を省く指定です。profile が適用された場合、生成された run config を次回以降も使います。

## 値と既定値

- 引数値・alias はありません。`argparse` の `store_true` で、未指定は `False`、指定すると `True` です（`setup.py:9199-9203`）。
- フラグ自体に数値・文字列の validation はありません。適用可否は後段の条件で判定されます。
- 既定状態では opt-in されません。setup は `STRATA_REPLICA_PROFILE` 環境変数でも profile 判定を試みます（`setup.py:10349-10357`; `strata_control/replica_profile.py:43-49`）。この環境変数は CLI 引数ではありません。

## 実行時の動作

setup は複数 GPU の選択がある場合に限り、`--replicas` が未指定で、`--layer-split` が未指定または `auto`、かつこのフラグまたは `STRATA_REPLICA_PROFILE` が有効なとき profile helper を呼びます。明示フラグがあれば `cfg["replica_profile"] = True` も記録します（`setup.py:10338-10357`）。

この root parser は macOS の通常 setup では使われません。`setup.py` は parser 作成前に `metal/setup_mac.py` へ委譲し、そちらは未知の引数を `not used on a Mac` と警告して続行します。従って Apple Silicon の Metal setup でこのフラグは適用されません（`setup.py:9068-9070`; `metal/setup_mac.py:356-358`）。

profile helper は次の条件を全て満たす場合に適用します（`strata_control/replica_profile.py:76-98`）。

- 2枚以上の GPU が選択されている。
- config が既に replica、`deepseek41`、`--peer-device` を指定していない。
- 自動 layer split を使い、engine 引数に `--layer-split` がない。
- model 名または engine 引数から Qwen3.8-Flash-Next と識別でき、quant が `IQ3_S`、`IQ3_XXS`、`Q2_0` のいずれか。
- 各 GPU の VRAM が24 GB以上。
- RAM 見積りで少なくとも2 engine 分を確保できる。

quant ごとの expert arena 見積りは IQ3_S 50.3 GB、IQ3_XXS 42.9 GB、Q2_0 34.0 GB、engine ごとの追加 RAM は8 GB、OS・server・file cache 用 headroom は12 GBです。Linux / Windows では arena を一度だけ共有する計算を使い、他 OS では replica ごとに expert copy を持つ計算を使います。作成数は RAM と GPU 数の小さい方で、選択 GPU の先頭から使います（`strata_control/replica_profile.py:30-38, 62-73, 87-97, 107-127`）。

適用時は `cfg["replicas"]` を GPU ごとに1枚ずつの group に設定し、Linux / Windows では `replica_shared_arena: true` を追加します。profile 用の `STRATA_*` engine 環境変数は、同名変数を現在のプロセス環境が設定していなければ既存 config 値を保ちつつ default として加えます（`strata_control/replica_profile.py:36-38, 111-121`）。

`--parallel` を明示した場合は profile 自体は適用されますが、自動値を設定しません。未指定かつ既存 config に `parallel` がなく、engine 引数に `--batch` / `--slots` がない場合は、2 replica なら8、その他は4を設定します（`setup.py:9192-9198, 10355-10357`; `strata_control/replica_profile.py:128-130`）。profile が適用されない場合、通常の4-card AMD profile を試す後続経路が残ります（`setup.py:10361-10370`）。

## 適用条件と副作用

- 明示的な `--replicas` または `--layer-split` の選択が優先され、この profile を適用しません。module 側でも既存の replica、peer device、別 model family、手動 layer split を拒否します（`setup.py:10349-10357`; `strata_control/replica_profile.py:80-89`）。
- RAM が2 engine 分に足りない、対応外の quant / model、1 GPU、24 GB 未満の GPU がある場合は適用されず、理由を表示して layer split を維持します。RAM 不足時の必要量は共有可能 OS で `12 + arena + 2*8 GB`、共有できない OS で `12 + 2*(arena + 8) GB` の見積りです（`strata_control/replica_profile.py:85-98`）。
- RAM に応じて選択 GPU が一部除外されることがあります。適用時は複数 engine 用の config、shared arena 指定、profile の engine 環境設定が作られ、config の書き込み後は通常の setup 経路で server を起動します（`strata_control/replica_profile.py:107-130`; `setup.py:10453-10454, 10483-10490`）。
- helper 内で予期しない例外が起きても setup は中止せず、`(the replica profile was not applied: ...)` と表示して継続します（`setup.py:10351-10362`）。helper 自体は渡されたカード情報・RAM・config の変換だけを行い、直接 I/O はしません（`strata_control/replica_profile.py:22, 101-130`）。

## 出力とエラー

helper が適用されると、engine 数・throughput の説明と共有 arena の説明を setup の通常メッセージとして出します。RAM により GPU が除外された場合は台数と RAM も表示します。profile 不適用の判定理由は通常メッセージとして表示し、helper の例外は括弧付きの案内として表示します。いずれもこの profile 判定単独では parser error や非0終了にせず、setup の後続処理へ進みます（`setup.py:10358-10362`; `strata_control/replica_profile.py:122-127`）。

## 根拠

- `setup.py:9192-9203` — root parser の `--parallel`、`--replicas`、`--replica-profile` 定義。
- `setup.py:10338-10370` — 複数 GPU 条件、helper 呼び出し、config 更新、例外処理と後続 profile。
- `setup.py:10453-10454, 10483-10490` — config / 起動 script の書き込みと setup 後の起動経路。
- `setup.py:9068-9070`; `metal/setup_mac.py:356-358` — Apple Silicon の委譲先 parser と未知引数の扱い。
- `strata_control/replica_profile.py:30-49, 62-98, 101-130` — quant、RAM 計算、適用条件、config 変換と通知内容。
- `setup.sh:6-13, 76`; `START-HERE.bat:8-10, 44-55` — POSIX / Windows wrapper が引数を `setup.py` に渡すこと。

この文書は指定 revision のソースを調査したものです。CLI `--help` は実行していません。異なる OS / backend での実動作や Release 配布物は確認していません。
