# `--feed`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点、working tree clean）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、update wrapper から委譲） |
| オプション | `--feed` |
| 別名 | なし |
| 値 | `URL` または `DIR`。parser は文字列として受け取る。 |

## 役割

DeepSeek-V4.1 用の独立 engine package を取得・更新するときに参照する署名付き update feed の場所を指定します。主にローカル feed を使ったテストや、release feed 以外の HTTPS feed を指定するための値です。`setup.py` の parser では `default=None`（既定値）で、値の形式や到達可能性を parser 段階では検証しません。

## 使い方

```sh
python setup.py --family deepseek41 --feed /path/to/local-feed
```

HTTPS feed を明示する場合は、`/path/to/local-feed` を feed の URL に置き換えます。引数の受け取りは `setup.py:9142-9144`、DeepSeek family から専用 setup に進む分岐は `setup.py:9613-9618` です。

## 値と既定値

`--feed` の値は `URL|DIR` として一つ受け取り、`choices`・型変換・独自 validation は指定されていません (`setup.py:9142-9144`)。値を省略した場合、DeepSeek engine の feed source は次の順で決まります。

1. 空でない `--feed` 値
2. 環境変数 `STRATA_UPDATE_FEED`
3. update 状態に保存された HTTPS feed（保存値が既定 feed の場合は platform 別既定値に解決）
4. release の既定 feed

この優先順位は `strata_cli/update_cmd.py:97-106` にあります。保存済み source のうち次回以降に引き継ぐのは HTTPS のみです (`strata_cli/update_cmd.py:109-111`)。空文字列は parser では受理されますが、`_feed_source()` の truth test では未指定と同じ扱いになります。

## 実行時の動作

DeepSeek-V4.1 を選び、適用可能な engine がまだなく、`--build` でも `--dsv41-package` でもない場合、`setup.py` は `--feed` 値を `get_dsv41_engine()` に渡します (`setup.py:8619-8626`)。既存の独自 engine を使っておらず、engine package が Strata 管理下にある場合は、起動前に feed を調べてより新しい package があれば更新を試します (`setup.py:8628-8630`)。feed からは現在の hardware に合う `dsv41` package を選び、取得・検証して `<data>/engine-dsv41/` 以下へ配置します (`setup.py:8173-8202`; `strata_control/dsv41_engine.py:150-179`)。

`--feed` の値がローカル path、`file://`、または loopback URL の場合、DeepSeek engine 取得前に行う GitHub 到達性チェックを省略します。これは feed がローカルであることを示すチェックであり、feed package の署名やファイル hash 検証を無効にしません (`setup.py:8137-8146`; 検証・取得経路 `strata_control/dsv41_engine.py:150-163`)。

この値は通常の Qwen engine の取得に転送されません。通常 engine の feed 取得は `setup.py:4553-4557` で `strata update --no-control --output json` を別プロセスとして起動し、その argv に `--feed` を加えていません。また CUDA 12 engine の driver floor を feed から読む経路も `Namespace(feed=None)` で source を解決するため、このオプション値を使用しません (`setup.py:1727-1738`)。

## 適用条件と副作用

- DeepSeek family の分岐でのみ engine package の取得・更新 source として利用されます (`setup.py:9613-9618`)。他 family では setup 全体の feed source を変更しません。
- `--dsv41-package` を指定した場合はその package を検証・導入し、feed 取得を行いません (`setup.py:8179-8183`)。`--build` 指定時も feed からの package 取得・更新を行いません (`setup.py:8624-8630`)。
- Feed package の取得時にはネットワークまたはローカル file access が発生します。正常導入後は `engine-dsv41` に新 package を置き、古い package directory を削除して一世代にします (`strata_control/dsv41_engine.py:162-179`)。更新時は新 engine を `--version` で起動確認してから古い世代を整理します (`strata_control/dsv41_engine.py:211-224`, `:227-233`)。
- macOS で `STRATA_CONTROL_INSTALL=1` でない場合、`setup.py` 自身の parser より前に `metal/setup_mac.py` へ argv を委譲します (`setup.py:9068-9069`)。その parser は未知引数を `not used on a Mac` と警告して続行するため、この `--feed` は通常の Mac setup では消費されません (`metal/setup_mac.py:356-358`)。

## 出力とエラー

ローカル feed でも署名付き feed の読込・package 選択・検証で失敗することがあります。取得できる DeepSeek package がない場合は理由を表示して engine 取得関数が `None` を返し (`strata_control/dsv41_engine.py:155-161`, `:180-182`)、setup は `no DeepSeek engine package could be fetched` と警告します (`setup.py:8199-8202`)。最後まで engine が得られない場合は「このコンピューターでは DeepSeek engine を利用できない」として失敗します (`setup.py:8640-8650`)。既存 engine の更新 feed に到達できない場合は更新を飛ばし、現在の engine で続行します (`setup.py:8205-8219`)。

## 根拠

- parser 定義: `setup.py:9142-9144`
- DeepSeek 用 feed source の優先順位: `strata_cli/update_cmd.py:97-111`
- ローカル feed 判定と GitHub 到達性チェック、取得・更新条件: `setup.py:8137-8146`, `:8617-8630`
- DeepSeek package の取得と失敗時の扱い: `setup.py:8173-8202`; `strata_control/dsv41_engine.py:150-182`
- 更新時の起動確認と旧 directory 整理: `strata_control/dsv41_engine.py:211-233`
- 通常 engine の別取得経路と CUDA 12 driver floor: `setup.py:4553-4557`, `:1727-1738`
- Apple Silicon の委譲と未知引数の扱い: `setup.py:9068-9069`; `metal/setup_mac.py:356-358`
