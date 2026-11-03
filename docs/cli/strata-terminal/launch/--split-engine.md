# `--split-engine`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--split-engine` |
| 別名 | なし |
| 値 | `auto`、`on`、`off` |

## 役割

モデルの各層を複数 GPU に分割して処理する通常の方式に代えて、全カードに全層の一部を持たせる all-cards split engine (`strata-split`) を起動するか、その選択規則を制御します。`auto` は対応条件を満たしたときだけ自動選択し、`on` は利用を明示的に要求し、`off` は使用しません。これは `strata launch` の設定用オプションであり、推論エンジン `strata` に直接渡すフラグではありません。

## 使い方

```sh
# 条件を満たす場合は split engine を自動選択（既定動作）
strata launch --model iq3_xxs --no-tui

# 利用可能なら split engine を要求し、使えない理由も表示
strata launch --model iq3_xxs --split-engine on --no-tui

# split engine を使わず、通常の layer split で起動
strata launch --model iq3_xxs --split-engine off --no-tui
```

## 値と既定値

- parser は `auto`、`on`、`off` のみを受理します。値は前後空白を除去し、小文字化してから検証します。そのため `ON` も `on` として受理されます。
- 省略時、argparse の値は未指定 (`None`) です。実行時の有効モードは `auto` になります。
- ほかの値や空文字列は parser エラーです。`argparse` が usage とエラーを stderr に出し、終了コード 2 で終了します。
- 同じオプションを複数回指定した場合は通常の `argparse` の `store` 動作に従い、最後に指定した値が残ります。

## 実行時の動作

`strata launch --split-engine VALUE` の値は `LaunchSettings.split_engine` に入り、通常の起動では run config の `split_engine` として保存されます。設定は preset にも含まれ、`--preset NAME` と他の起動フラグを併用した場合、フラグの変更はその起動だけに適用されます。`--save-preset NAME` を指定すると設定を preset として保存します。

run config の値より環境変数 `STRATA_SPLIT_ENGINE` が優先されます。値が `on/1/true/yes` のいずれかなら有効、`off/0/false/no` なら無効です。大文字小文字と前後空白は無視されます。環境変数が空または未設定なら run config が使われ、どちらの値も認識できない場合は `auto` になります。従って `--split-engine on` を指定しても、`STRATA_SPLIT_ENGINE=0` があると無効になります。

`auto` では、Linux 上で同一メーカー・同一型・同一メモリ容量の 2〜4 枚の GPU を使い、モデル形式・メモリ量・カード構成などの規則を満たす場合に限り split engine を選びます。対象モデルは Qwen3.8-Flash-Next の 48 層・512 experts 構成で、split engine が読める tensor type であること、全 experts が VRAM に収まり、必要な空き RAM があることも判定されます。確認済みの構成は NVIDIA sm_86 の2枚、AMD gfx1201 の2〜4枚です。さらに Auto は NVIDIA では compute capability 86/120 以外を選ばず、AMD では gfx1201 の4枚構成かつ routed expert type が `Q4_K`、`Q5_K`、`Q5_1`、`Q8_0` の場合に限定されます。条件を満たさない場合、Auto は通常の layer split を選び、通常は理由を表示しません。

`on` は同じ基本条件で split engine を要求し、通常の利用条件を満たさない場合は理由を一行表示します。AMD の対応ビルド対象アーキテクチャで未検証のものも明示指定時には候補となり、engine 自身が起動時 self-test を行います。`off` は split engine の判定を行わず、通常の layer split を使います。

split engine が選択された場合、Terminal は engine component と同じディレクトリからカード数・GPU architecture に対応する `strata-split-*` 実行ファイルを探します。split はモデル自身の MTP draft layer を使うため、drafting が `dflash2` または `off` の場合は通常方式になります。split 用設定では MTP、context、vision、batch/lane 数などを引数として構成し、元の通常方式の設定も fallback 用に保持します。`--parallel N` がある場合は split engine の lane 数として使われます。

## 適用条件と副作用

- split engine は Linux 専用です。カードは2〜4枚で同一メーカー・同一モデル・同じ VRAM 容量が必要です。混在カード、非対応 GPU、非対応モデル形状や tensor type、GPU/RAM 不足、対応 binary の欠落などでは選択されません。
- 現行の Auto は NVIDIA では2枚構成を確認済みの sm_86 / sm_120 に限定し、AMD は gfx1201 で4枚・指定 expert type の場合だけです。ほかの AMD architecture は明示的な `on` が必要です。`on` も、Linux、カード数・メーカー、対応する build architecture、モデル形式などの基本制約を解除するものではありません。
- MTP draft layer が未ダウンロードなら split engine は起動しません。`on` では MTP を取得するため `--drafting mtp` を指定するよう警告し、通常方式に切り替えます。Auto ではこの不成立を静かに扱います。
- 起動時に GPU、モデル GGUF、カード数に合う split engine binary、および `draft_vocab_en.bin` の所在を確認します。split 設定では `FNX_ARENA=0` と `FNX_EXPERT_RAM_GIB=off` を engine 環境に設定し、全 experts を GPU memory に置く構成にします。
- `--plan` は起動計画の表示だけで、実際の起動・GPU 実行はしません。split の事前判定は、未取得のモデルや engine package について一部の情報を仮定するため、計画上の予測は実際の起動時判定と異なることがあります。

## 出力とエラー

- `auto` で条件を満たさない場合は原則として通知せず通常の layer split に進みます。`on` の拒否条件は理由を含む一行として通知され、launch 自体は停止しません。
- split engine が選択されても起動に失敗または拒否された場合、server は保持した通常方式の設定で起動を試みます。Terminal は split 起動失敗の警告を表示し、ログに理由があれば併記します。
- 不正な option 値は parser が拒否し、終了コード 2 になります。その他の起動失敗時の終了コードは、このオプション単独では決まりません。

## 根拠

- `strata_cli/launch/cmd.py:37-45,108-111,251-252` — 値の正規化・検証、parser 宣言、設定への反映。
- `strata_cli/launch/settings.py:29-30,128,351-352` — 許容値、未指定時の設定、表示用フラグ化。
- `strata_cli/launch/runner.py:533-550,1608-1627` — run config への設定保存と split 判定の呼び出し順。
- `strata_cli/launch/runner.py:1630-1682` — platform/既存 MTP/binary の確認、判定、警告と通常方式への切替。
- `strata_control/split_engine.py:48-64,176-247,377-390` — 検証済み構成、自動選択条件、GPU/RAM・モデル適合性の判定。
- `strata_control/split_engine.py:356-369` — 既定 `auto` と環境変数 `STRATA_SPLIT_ENGINE` の優先順位・値の解釈。
- `strata_control/split_engine.py:451-513` — run config とモデル条件の判定、binary / MTP / vocabulary 確認、split 用 config の生成。
- `strata_control/split_engine.py:250-270` — split engine に渡す引数・環境変数と fallback 用 config。
- `serve/server.py:9104-9144` — split engine の起動失敗時に通常方式を起動する処理。
- `strata_cli/launch/runner.py:2204-2219` — fallback 発生時の Terminal 通知。
- `strata_cli/launch/cmd.py:307-309,993-997` — `--save-preset` と、`--preset` に重ねた一時変更の保存規則。

調査範囲は上記 checkout のソースです。Release artifact や実機での GPU 起動は確認していません。
