# `--skip-build`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などから委譲） |
| オプション | `--skip-build` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時 `True`、省略時 `False` |

## 役割

このオプションは parser に受理されますが、この commit の `setup.py` では解析結果 `a.skip_build` を参照する処理がありません。したがって、名前から想像される「ビルドをスキップする」効果はソース上で確認できず、現在は実行動作を変えない受理済みフラグです。parser のヘルプ表示からも隠されています。

## 使い方

Linux で `setup.sh` 経由に渡す例です。`--check` は PC の確認だけを行います。`--skip-build` 自体が確認処理やビルドの有無を変えるわけではありません。

```sh
./setup.sh --skip-build --check
```

## 値と既定値

- 値は不要です。値を続けて指定する形式ではありません。
- `argparse` の `store_true` により、指定時は真、未指定時は偽です。
- 明示的な値検証や追加の条件分岐はありません。未知の引数・必要な値の不足など、他の parser エラーは通常の `argparse` の処理対象です。
- `help=argparse.SUPPRESS` のため `setup.py --help` の通常のオプション一覧には表示されません。

## 実行時の動作

`setup.py` の root parser はこのフラグを受け取りますが、ソース全体で `skip_build` の参照は定義箇所だけです。実際のビルド選択は別の `a.build` を使い、`--build` が指定された場合は既成エンジンを選ばずビルドへ進みます。AMD の一部経路でも `a.build` を見て既成エンジンの取得を切り替えます。このため `--skip-build` はこれらの判断に作用しません。

また、CPU が AVX2 を持たない経路では setup が `a.build = True` に設定してソースビルドを選択します。この自動設定も `a.skip_build` を参照しません。更新モードのエンジン更新分岐も `a.build` を参照します。

## 適用条件と副作用

- Linux/Windows の wrapper は引数を `setup.py` へ渡すため、この parser 経路では受理されます。SYCL 経路も argv を保持して `setup.py` を再実行します。
- macOS で `CONTROL` が無効の場合、`main()` は root parser を作る前に `metal/setup_mac.py` へ引数を渡します。このとき `--skip-build` が受理されるかは別 parser の実装に依存し、本調査ではその parser の挙動をこの root option のものとして扱いません。
- `CONTROL` が有効な macOS 経路では root parser を通りますが、フラグを消費する処理は見つかりません。
- このフラグ自身がファイル、ネットワーク、子プロセス、エンジン build に及ぼす副作用は確認できません。後続の setup 処理が行う副作用は、他の引数と実行環境によります。

## 出力とエラー

`--skip-build` 固有の出力・警告・失敗経路は確認できません。parser が隠しオプションとして受理し、値を読むコードもないためです。引数として受理されること以外の効果はありません。

## 根拠

- parser 定義（`store_true`、ヘルプから抑制）と直後の parse: `setup.py:9211-9212`。
- root parser より前に通常 macOS 経路を別 setup へ委譲: `setup.py:9068-9070`。root parser を通過後の Control Mac / SYCL 分岐: `setup.py:9220-9225`。
- 更新時のエンジン取得は `a.build` で分岐: `setup.py:7034-7038`。
- AMD Windows の既成エンジン選択、および通常経路の既成エンジン／ソースビルド選択: `setup.py:7779-7799`。
- CPU 条件により `a.build` を自動設定: `setup.py:9529-9540`。
- setup wrapper が `setup.py` に引数を渡す例: `setup.sh:9-12`、`START-HERE.bat:44-54`。SYCL setup は argv を再利用して `setup.py` を呼び直す: `sycl/setup_intel.py:547-560`。

調査では `setup.py` の全参照検索を行い、`skip_build` は parser 定義以外に見つかりませんでした。別の OS / Control モード固有 parser の解釈は、この root parser からは確認していません。
