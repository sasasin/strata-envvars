# `strata components plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components plan` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/components.py`、`strata_control/targets.py` |
| 位置引数 | `manifest` — コンポーネント manifest の JSON ファイル |

## 役割

コンポーネント manifest を読み込み、manifest に記された platform と backend が照合対象で利用可能な組み合わせかを表示します。互換性確認だけを行い、パッケージの取得・展開・有効化はしません。

## 使い方

```sh
# 現在の OS・アーキテクチャと照合し、人向けに結果を表示
strata components plan ./component.json

# 照合する backend と platform を明示
strata components plan ./component.json --backend cuda --target linux-x86_64

# 機械処理向け JSON を出力
strata components plan ./component.json --output json
```

`manifest` は必須です。利用可能な形式は `--output human`（既定）と `--output json` です。

## 実行モードと出力

- **human**: component ID、version、kind、platforms、target、payload サイズ、cache key の先頭 16 文字、互換性、拒否理由を表示します。`--backend` を指定した場合はその値も表示し、requires があれば併記します。
- **json**: `schema_version: 1` と、component の ID・version・kind・backend・target・platforms・cache key・`usable`・`reasons`・artifacts・合計 bytes・requires・entrypoint を含むオブジェクトを出力します。
- どちらの形式も正常に manifest を処理した場合の終了コードは 0 です。互換性がない場合も処理自体は成功し、`usable` が false（human では `NO`）となり、理由が示されます。

このコマンドは manifest を読むだけで、何もダウンロード・展開・変更しないと実装に明記されています。

## 主な動作と注意点

- `--target` を省略すると `host_platform()` が現在の OS・アーキテクチャを `macos-arm64`、`linux-x86_64` などのキーに変換します。値を指定した場合はその文字列を platform キーとして照合します。指定値の形式を CLI 側で別途検証する parser はありません。
- `--backend` は任意の文字列を受け取ります。manifest に backend がある場合、指定値との不一致が拒否理由になります。backend 指定を省略しても、manifest が backend を宣言していれば、その backend と target の対応表によるサポート確認は行われます。manifest に backend がない場合、`--backend` は照合結果に影響しません。
- backend の対応表は `metal` = `macos-arm64`、`cuda` / `hip` = `windows-x86_64` と `linux-x86_64`、`sycl` = `linux-x86_64`、`cpu` = 4 種の macOS / Windows / Linux x86_64・macOS arm64 です。これはソースに定義されたサポート行列の確認であり、実機 GPU、driver、実際の導入状態を検査するものではありません。
- `--target` は別マシン向けの manifest を検査するための照合値です。target を現在のホストと違う値にしても、そこでパッケージが実行できることを保証しません。
- manifest は schema version 1、既知の kind、component ID、artifact 名・SHA-256・正の byte 数、および空でない platforms を要求します。JSON 不正、必須項目不足、不正な digest などは manifest エラーになります。各 artifact の format、URL の到達性、実際のファイル digest はこの計画表示でダウンロード検証されません。

## 出力とエラー

- manifest のパスが存在しない場合、human 出力では stderr に `strata: no component manifest at ...` を出し、終了コード 2 を返します。JSON 出力では `schema_version: 1`、`ok: false`、`error.code` と `error.message` を含む JSON を stdout に出します。
- 不正 JSON や schema / manifest 検証エラーは `ComponentError` の code（既定値 6）で失敗します。human では `strata: ...` を stderr、JSON では同じエラー envelope を stdout に出します。
- 読み込み時の `OSError` は共通処理で整形されて終了コード 6 になります。JSON の場合は `ok: false` のエラー JSON です。
- `--output` に `human` / `json` 以外を指定すると argparse が引数エラーとして拒否します。
- OS が `host_platform()` で扱う Darwin、Linux、Windows 以外の場合、既定 target の解決時に `ComponentError` となります。明示的な `--target` を指定すると host platform 解決は不要です。

## 関連文書

- [CLI オプション索引](../../../README.md) — `--backend`、`--output`、`--target` の個別文書へのリンク。
- [`strata components` 概要](../README.md)
- [`strata components backends` 概要](../backends/README.md)

## 根拠

- Strata `strata_cli/cli.py:114-128` — `components` / `plan` の階層、位置引数と `--backend`、`--target`、`--output` の parser 定義。
- Strata `strata_cli/cli.py:1966-2011` — manifest の読み込み、既定 target、互換性判定、JSON / human 出力、および読み取り専用の説明。
- Strata `strata_cli/cli.py:527-542,2129-2130,2166-2183` — エラー出力形式、コマンド dispatch、`ValueError` / `OSError` の終了コード処理。
- Strata `strata_control/components.py:52-57,136-228` — schema version、component kind、manifest 検証、cache key と互換性判定。
- Strata `strata_control/targets.py:12-18,20-51` — `ComponentError` の既定 code、backend 対応表、host platform と backend support の判定。

## 調査範囲

指定 checkout の commit と作業状態を確認し、上記の Python parser・処理・互換性 helper を調査しました。別 platform 上での実行、配布済み Release の CLI、実際のパッケージ取得や導入後の動作は確認していません。
