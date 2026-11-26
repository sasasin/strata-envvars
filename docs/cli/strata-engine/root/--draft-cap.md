# `--draft-cap`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（索引上の scope: `root/`） |
| オプション | `--draft-cap` |
| 別名 | なし |
| 値 | 整数 `N`。正数は DFlash2 の検証窓の上限、0 以下はカード別自動判定 |

## 役割

`--draft dflash2` を使用する際に、`--spec` が指定する検証窓を何トークンまで許すかを指定します。省略または 0 以下なら GPU 情報を使ってカード別の上限を選び、明示した正数ならその値を上限にします。このオプション自体は `--spec` を増やさず、カード別の上限値だけを置き換えます。

## 使い方

```sh
# DFlash2 の検証窓を最大 6 トークンにする例（pack、MTP の語彙ディレクトリ等は利用環境に合わせる）
strata generate --pack model.strata --tokens "1,2,3" --mtp mtp-dir --draft dflash2 --draft-model drafter.pack --spec 8 --draft-cap 6
```

## 値と既定値

- 既定値は `0` です。未指定時も同じ値になり、カード別の自動判定に進みます。
- parser は値を `std::atoi` で整数化し、`std::max(0, ...)` で 0 未満を 0 に補正します。したがって数値として読めない文字列も `atoi` の結果 0 となり、自動判定になります。専用の形式・範囲エラーはありません。
- 値を省略すると `--draft-cap needs a value` を stderr に出して終了コード 2 で終了します。
- 同じ引数を複数回指定した場合、引数解析のたびに値を代入するため最後の指定が残ります。
- 正数に対する明示的な上限検査はありません。実際には `--spec` がその値を超えるときだけ `--spec` を下げます。

## 実行時の動作

この処理は DFlash2 が有効なビルドで、`--draft dflash2` の初期化に成功した後に行われます。明示値が正ならその値を、そうでなければ `dflash2_auto_cap()` の結果を上限として選びます。上限が正で `--spec` がそれを超えていれば `--spec` を上限まで下げます。上限が 0 の場合は `--spec` を変更しません。従って `--spec` が上限以下なら何も変化せず、このオプションだけで窓を拡大することはありません。

自動判定の現行実装は次のとおりです。

| GPU 条件 | 自動上限 |
| --- | ---: |
| gfx1151 UMA（Strix Halo / iGPU として判定） | 8 |
| CUDA compute capability 12.x（Blackwell）かつ VRAM が 15,000,000,000 bytes 以上 | 8 |
| その他の Blackwell | 6 |
| その他 | 0（`--spec` の指定を維持） |

HIP ビルドでは compute capability と VRAM byte 数を 0 として判定関数に渡し、gfx1151 UMA 判定だけが 8 の自動上限になり得ます。CUDA の device property 取得に失敗した場合は上限判定と窓の補正を行いません。明示した正数は自動判定結果を置き換えるため、カードクラス既定より大きい上限を指定することもできますが、実際の窓は `--spec` 以下です。

自動上限によって窓を縮めた場合は stderr に適用上限と理由を出します。CUDA の 13 GiB 未満のカードでは、自動設定時に MTP の方が多くの測定で速かった旨の注意も出しますが、処理は継続します。明示的な `--draft-cap` を指定した場合、この注意は出ません。

## 適用条件と副作用

- DFlash2 経路専用です。既定の MTP drafter や、DFlash2 の利用条件が成立せず MTP にフォールバックした経路ではこの上限処理に入りません。
- 起動時の DFlash2 load 成功後に上限判定します。load 失敗時は fallback の有無に応じて MTP へ切り替えるか、起動を失敗させます。この場合 `--draft-cap` は窓を変更しません。
- `--draft auto` は serve 用の別経路を持ちますが、この parser のコメントでは CLI が `auto` を DFlash2 として扱うとされています。ここで確認した上限適用箇所は `o.draft == "dflash2"` の起動分岐です。serve のリクエスト単位選択でこの上限がどう反映されるかは、この箇所だけでは確定できません。
- 窓を補正する際は stderr 出力と `o.spec` の起動時変更が発生します。ファイルやネットワークへの副作用はこのオプションの処理箇所では確認できません。

## 出力とエラー

- 値なしは stderr に不足を表示し、終了コード 2 です。
- 正の上限によって `--spec` を縮める場合は stderr に `windows capped at ... tokens` を出します。
- DFlash2 が起動できない場合のエラーや MTP fallback の説明は DFlash2 側の起動条件・load 結果によって決まり、このオプション固有の validation error ではありません。

## 根拠

- `engine/src/program/generate.cpp:1198` — `draft_cap` の既定値 0 と用途。
- `engine/src/program/generate.cpp:1361-1369` — help 表示上のオプション説明（補助資料）。help は Blackwell cc 12.0 の 8 上限条件を「48 GB 以上」と記しますが、現行判定関数は 15,000,000,000 bytes 以上を条件にしており、help 表示と実装に差があります。
- `engine/src/program/generate.cpp:3842-3847` — 値引数の不足時に stderr と終了コード 2 で終了する共通処理。
- `engine/src/program/generate.cpp:4162-4163` — parser 定義。`atoi` による変換、負数を 0 にする補正、重複時の代入。
- `engine/src/program/generate.cpp:8266-8303` — DFlash2 有効経路、device 情報取得、明示値と自動値の選択、`--spec` の縮小と stderr 通知。
- `engine/src/program/generate.cpp:8304-8308` — CUDA 13 GiB 未満での自動設定時の注意出力。
- `engine/include/strata/core/draft_cap.hpp:8-32` — Blackwell の VRAM byte 閾値とカード別自動上限。
- `engine/src/program/generate.cpp:8310-8326` — DFlash2 load 失敗時の fallback / 起動失敗、および MTP 用窓への補正。

調査では parser、上限計算、起動時の適用箇所を確認しました。GPU 実機での挙動確認や build・テストは行っていません。
