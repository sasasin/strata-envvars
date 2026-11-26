# `STRATA_MTP_STAGE0`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の複数 GPU layer split で `--pipeline-windows 2` を使うとき、MTP drafter を最後の stage ではなく最初の GPU に置くかを指定する。最初の GPU に置くと、window を終えた stage 0 の GPU が次の draft chain を実行し、最後の GPU で window と draft chain が同居するのを避ける。変数は MTP の有無や pipeline 自体を有効化せず、配置だけを選ぶ。`generate.cpp` の構成時に読み取られる（`engine/src/program/generate.cpp:6732-6737, 8254-8265`）。

## 値と判定

値は `std::atoi` で整数化し、結果が 0 かどうかだけを見る。文字列全体の検証や範囲制限はない。未設定なら build と GPU に応じた既定値を使う。明示した値は既定値を上書きする。

| 条件 | unset | 最初の GPU を選ぶ値 | 最後の GPU を選ぶ値 |
|---|---|---|---|
| 対応条件を満たし、値を設定 | 該当なし | `atoi` 結果が非 0（例: `1`, `-1`, `1tail`） | `atoi` 結果が 0（例: `0`, `0tail`, 空文字, `true`, 数字で始まらない文字列） |
| 値が未設定 | HIP build かつ現在の device が gfx1200/gfx1201 なら最初、それ以外は最後 | 既定判定による | 既定判定による |

`atoi` のため、先頭の空白と符号の後にある数値部分を読み、後続文字は無視する（例: `  +2xyz` は非 0、`0anything` は 0）。`true` / `false` は真偽値として解釈されず、どちらも 0 になる。整数として読めない値も 0 になる。負値も 0 以外なら最初の GPU を選ぶ。値の境界 clamp やエラー報告はない（`engine/src/program/generate.cpp:6732-6737`）。

未設定時の既定は HIP build で `decode_defaults_arch_ok()` が成功すると true、その他の build では false。HIP 側の判定は現在の device のアーキテクチャが gfx12 WMMA（gfx1200/gfx1201）かどうかである（`engine/src/program/generate.cpp:2849-2857, 2860-2868`）。

## 有効になる条件

- `--pipeline-windows` が 2 以上であること。CLI 値は 0〜2 に clamp され、未指定時の自動設定は `STRATA_PIPELINE_AUTO`、serve 状態、GPU split、build など別条件で決まる。`--pipeline-windows 0` / `1` ではこの変数による配置切り替えは行わない（`engine/src/program/generate.cpp:4119, 6560-6583, 6732-6736`）。
- `--mtp` が指定され、`--spec` が 2 以上であること。さらに `--mtp-draft-vocab` が指定されていればそのファイル、なければ MTP directory 内の `draft_vocab.bin` が存在すること。条件を満たさなければ常に最初の GPU 配置を不可とする（`engine/src/program/generate.cpp:6540-6546`）。
- `STRATA_MTP_FULL_HEAD` が先頭文字 `1` で設定されていないこと。これに当たると最初の GPU 配置は不可。値の残り部分は検査しない（`engine/src/program/generate.cpp:6540-6546`）。
- pipeline 用 stage が存在し、`--batch` が使われていないか、`STRATA_PW_WITH_BATCH` の先頭文字が `1` であること。後者の場合 pipeline は solo path では有効でも、batch windows は対象外（`engine/src/program/generate.cpp:6555-6559, 6732-6736`）。
- pipeline 自体は `--serve` と複数 GPU の layer split を要し、helper cache や `--peer-device` などの条件でも無効化されうる。これらにより pipeline が無効なら配置指定も効果を持たない（`engine/src/program/generate.cpp:6573-6601`）。

明示的な `STRATA_MTP_STAGE0` は、最初の GPU 配置が可能なとき HIP 以外の build でも既定判定を上書きする。未設定時の auto pipeline は HIP build 以外では無効化されるが、明示した `--pipeline-windows 2` の MTP 配置判定には build macro による拒否分岐がない（`engine/src/program/generate.cpp:6567-6571, 6732-6736`）。

## 実行時の詳細

変数名の直接参照は `engine/src/program/generate.cpp` に 2 箇所ある。明示的に `--pipeline-windows 2` を指定した二段 split では、最初に `first_card` を評価して推奨 note の要否を判定し、その後 stage 構築時に `mtp_first` を計算して実配置を決める。`mtp_first` 判定は一度だけ行われ、static cache やリクエストごとの再読込はない。プロセス起動後に環境値を変更しても、この engine 構成に反映されない（`engine/src/program/generate.cpp:6605-6617, 6732-6737`）。

`mtp_first` が true のとき、MTP loader は stage 0 の device/session 上で動作し、その device の weights と draft head に bind される。false なら最後の stage の device/session を使う（`engine/src/program/generate.cpp:8254-8265, 13496-13503`）。pipeline 使用時の MTP の row buffer も配置先に合わせて確保される（`engine/src/program/generate.cpp:13467-13480`）。

この変数は2段 split の明示的 pipeline で、実際には最初の GPU 配置ができない場合、note に理由を出す。ただしその判定は環境値の変換とは別で、たとえば MTP や subset vocab file がないと値が非 0 でも配置されない。既定で最初の GPU 配置になるかどうかと、明示設定の効果を混同しないこと（`engine/src/program/generate.cpp:6605-6617, 6732-6736`）。

## ログと測定値

二段 split で明示的に `--pipeline-windows 2` を指定し、MTP を最初の GPU に置けない場合は、stderr に `strata generate: note: --pipeline-windows ...` で始まる note が出る。MTP 条件が欠ける場合は理由として `it needs --mtp with --spec 2 or more and the draft head's subset file (draft_vocab.bin)`、条件を満たすのに配置しない場合は `STRATA_MTP_STAGE0=1 asks for it` が表示される。pipeline は要求どおり維持される（`engine/src/program/generate.cpp:6605-6617`）。

このコード経路には、環境変数値自体のログ、無効値警告、または環境変数だけを理由にした終了処理はない。MTP load や pipeline の別の初期化失敗は個別のエラー経路を持つ（`engine/src/program/generate.cpp:8264, 13435-13483`）。測定値は記載しない。コメントと `docs/MULTI_GPU.md` には配置の設計説明があるが、本書では性能を実測した結果として扱わない。

## 根拠

- `engine/src/program/generate.cpp:2849-2868` — 既定の HIP / gfx12 判定。
- `engine/src/program/generate.cpp:6540-6546` — MTP、speculative depth、draft vocab file、`STRATA_MTP_FULL_HEAD` の配置適格性。
- `engine/src/program/generate.cpp:6555-6583, 6584-6617` — batch 条件、pipeline の自動・明示条件、診断 note。
- `engine/src/program/generate.cpp:6732-6737, 8254-8265` — 環境値の判定と MTP 配置。
- `engine/src/program/generate.cpp:13467-13503` — pipeline row buffer と MTP bind。
