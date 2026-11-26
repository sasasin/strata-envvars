# `--window-hashes`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root 引数） |
| オプション | `--window-hashes` |
| 別名 | なし |
| 値 | 出力ファイルのパス (`PATH`) |

## 役割

speculative decoding の verify 窓ごとに、最終残差行列の 64 bit ハッシュと argmax token ID 列を記録します。異なるビルドや speculative 設定を比較する診断・ベンチマーク向けの出力です。単発推論の speculative loop が実行される場合に書き込みます。

## 使い方

```sh
# 例: token ID 列を使う単発推論の verify 窓を記録する。
# pack、PLE、token ID は実際のモデルと環境に合わせる。
strata --pack pack/full --tokens "1,2,3" --ple-gguf /path/to/ple.gguf \
  --spec 4 --adapt-every 0 --window-hashes /tmp/window-hashes.txt
```

このオプションだけでは speculative loop は開始しません。`--spec` など推論条件が整い、生成可能な token が残っていて、EOS で終了していない場合に記録されます。

## 値と既定値

`PATH` は次の argv 要素から文字列として受け取り、パーサー段階では形式や書き込み可能性を検証しません。値を省略すると `--window-hashes needs a value` を stderr に出して終了コード 2 で終了します。複数回指定した場合は、引数走査で後から代入されたパスが使われます。空文字列は受理されますが、空の値は未指定と同じ扱いになりファイルを開きません。

既定値は空文字列（出力なし）です。speculative loop に入ると、指定パスを `fopen(..., "w")` で開くため、既存ファイルは切り詰められます。親ディレクトリは作成されません。

## 実行時の動作

speculative loop の開始後、窓の処理に先立って出力ファイルを開きます。開けない場合は `strata generate: cannot write <PATH>` を stderr に出し、終了コード 1 を返します。各 verify 窓の処理が成功すると、次の空白区切りの1行を追記します。

```text
ラウンド番号 位置 窓サイズ 16桁の16進ハッシュ argmax-token-ID ...
```

ハッシュ対象は窓の最終残差行列を float のバイト列として並べたものです。実装は FNV-1a の初期値 `1469598103934665603` と乗数 `1099511628211` を使います。行の後半には窓の各位置の `outv`（verify 結果の argmax token ID）が出力されます。`--spec-follow` が指定されていても、記録は follow の token ID で `outv` を置き換える処理より前に行われます。

`--window-hashes` 自体は推論結果や採択判定を変更しません。help はビルド間の比較用途として `--spec-follow` と `--adapt-every 0` を併用する例を案内しています。`--adapt-every 0` は適応的な cache 更新を止める設定ですが、ハッシュ出力オプションの必須条件ではありません。

## 適用条件と副作用

- 対象は `strata-engine` の root 引数です。Terminal CLI の同名 `strata` wrapper のオプションではありません。
- 記録処理は speculative loop 内にあります。loop は開始位置が設定され、`produced < max_new` かつ EOS 終了済みでない場合に実行されます。したがって、loop が実行されない経路ではファイルを開かず、出力しません。
- 通常の `engine/src/program/generate.cpp` と SYCL 用 `engine/sycl/src/program/generate.cpp` の双方に同じ用途の parser・書き込み処理があります。実際に使われる実装はビルドされた engine/backend によります。
- ファイルは指定先に作成または上書きされます。処理途中で別のエラーが起きると、すでに書いた行だけが残る可能性があります。書き込みや `fclose` の戻り値を検査するコードは確認できません。

## 出力とエラー

- 値がない場合: `--window-hashes needs a value`、終了コード 2。
- 出力ファイルを開けない場合: `strata generate: cannot write <PATH>`、終了コード 1。
- 窓の verify が失敗した場合などは通常の推論エラー経路で終了し、ファイルにはそれまでの行が残ることがあります。
- 行書き込み後のディスクエラーやクローズ失敗について、専用の診断・終了コード処理はソースで確認できません。

## 根拠

- `engine/src/program/generate.cpp:1034-1035` — オプション値の格納先。
- `engine/src/program/generate.cpp:1396-1401` — help 上の用途と `--spec-follow`、`--adapt-every 0` との使用例。
- `engine/src/program/generate.cpp:3842-3847,4053-4058` — argv 値取得、値の不足処理、オプション parser、関連する `--spec` と `--adapt-every` の parser。
- `engine/src/program/generate.cpp:24464-24489`、`engine/include/strata/spec/spec_start.hpp:14-18` — speculative loop の開始条件と loop 前の失敗経路。
- `engine/src/program/generate.cpp:24859-24866,25149-25165,25250-25256` — ファイルの open/truncate、verify 窓ごとのハッシュと token ID の書き込み、follow 適用順、close。
- `engine/sycl/src/program/generate.cpp:13981-13989,14139-14156,14233-14238` — SYCL 実装の対応するファイル処理。
- `docs/cli/000_cli_tools.md:7-10`、`docs/cli/README.md:1036-1041,1233` — tool ID/parser scope と、作成対象リンクの配置。

この調査では既存バイナリの help 表示や実行、ビルド、GPU 動作を確認していません。値の検証を行わない範囲、書き込み失敗時の戻り値未検査、実行時の backend 差はソースから確認できる範囲に限って記載しました。
