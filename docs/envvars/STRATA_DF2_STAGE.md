# `STRATA_DF2_STAGE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

明示的に DFlash2 drafter を使う複数 GPU の layer split で、drafter の配置先を選びます。値が `first` のときは最初の stage の GPU に置き、それ以外では最後の stage の GPU に置きます。コードコメント上も測定用の選択点であり、既定の配置ではありません。

これは DFlash2 を有効にする設定ではありません。DFlash2 を使うかどうかは `--draft dflash2` などで決まり、この変数はその後の配置を選びます。単一 GPU、`--draft auto`、stage のない経路では環境変数を読みません（`src/program/generate.cpp:5561-5567`）。

## 値と判定

| 値 | 判定・配置 |
|---|---|
| 未設定 | `df2_first=false`。最後の stage に配置 |
| 空文字 | `std::string("") == "first"` が偽。最後の stage に配置 |
| `first` | 完全一致し、最初の stage に配置 |
| その他（`FIRST`, `First`, `first `, `0`, `1` を含む） | 完全一致しないため最後の stage に配置 |

数値変換や前後空白の除去はありません。無効な文字列への警告やエラーもなく、既定の last-stage 配置にフォールバックします。`getenv` の読み取りは `multi_gpu` が真、`stages` が空でなく、`o.draft == "dflash2"` かつ `o.draft_auto` が偽の場合に限られます。

## 有効になる条件

- DFlash2 対応コードがビルドに含まれ、DFlash2 が実際に利用可能であること。初期化・利用箇所は `STRATA_HAVE_DFLASH2` の条件付きコードです（`src/program/generate.cpp:6765-6766`）。
- 複数 GPU の layer split があり、少なくとも 2 stage あること。
- `--draft dflash2` を明示し、`--draft auto` ではないこと。
- `--pipeline-windows` が有効な場合、DFlash2 は使われず、環境変数の配置選択も利用効果を持ちません。通常は MTP にフォールバックしますが、`--draft-fallback none` では代替 drafter がないため起動を終了します（`src/program/generate.cpp:6767-6771,6802-6818`）。

これらの条件外では `STRATA_DF2_STAGE=first` を設定しても DFlash2 の起動や layer split の有効化は行いません。

## 実行時の詳細

判定は `generate` の stage 構成後に一度行い、その結果をローカルの `const bool df2_first` として後続の配置処理で使います。関数内の static cache ではありませんが、同じ実行経路の途中で環境変数を変更しても、この判定はやり直されません（`src/program/generate.cpp:5561-5567`）。

`--layer-split auto` の stage ごとの空き VRAM 見積もりでは、`df2_first` が真なら drafter 分の余地を先頭 stage に、偽なら最終 stage に見込みます（`src/program/generate.cpp:5715-5731,5733-5746`）。DFlash2 pack のロード先も、真なら device 0、偽なら最後の stage の device です（`src/program/generate.cpp:6772-6774`、`src/core/dflash2.cpp:127-130`）。

layer split の DFlash2 初期化では、真なら CUDA0 側の weight table を使い、偽なら最後の stage の weight table を使います。head は最後の stage の head を渡し、drafter と head が別 GPU で vocabulary subset の行が必要な場合は、head 側で行を集めて drafter 側へコピーします。stage の taps はどちらの配置でも drafter の GPU に集めます（`src/program/generate.cpp:11146-11157,11170-11175`、`src/core/dflash2.cpp:310-323,342-379`）。

起動成功時の stderr ログには DFlash2 の device 番号と `first` / `last` stage のどちらかが表示されます。初期化できない場合は理由を stderr に出して MTP にフォールバックします。`--draft-fallback none` で MTP がない場合は、その理由を出した後に起動を終了します（`src/program/generate.cpp:11160-11175,6802-6818`）。環境変数の値自体を報告するログや、未知値を拒否する処理はありません。

## 根拠

- 変数の読み取り、適用条件、完全一致判定: `src/program/generate.cpp:5561-5567`
- 自動 split の drafter 用 VRAM 見積もり: `src/program/generate.cpp:5715-5731,5733-5746`
- DFlash2 build guard、load device と pipeline 制約、失敗時の fallback: `src/program/generate.cpp:6765-6774,6802-6818`
- stage 上の weights/head/taps の結び付け、起動ログと失敗ログ: `src/program/generate.cpp:11146-11175`
- pack の device 設定と GPU allocation: `src/core/dflash2.cpp:127-130`; head 行の転送: `src/core/dflash2.cpp:310-323,342-379`

`docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。性能値や配置の優位性は、このソース調査では確認していません。
