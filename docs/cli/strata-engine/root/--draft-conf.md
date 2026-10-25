# `--draft-conf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--draft-conf P` |
| 別名 | なし |
| 値 | 数値 `P`。parser は `std::atof` で読み、`0.0`〜`1.0` に clamp する |

## 役割

`--draft dflash2` を使うとき、DFlash2 の selector が出す各 draft の確率を先頭から掛け合わせ、その積が指定値を下回る位置で検証 window を終えるための下限値です。`--draft-conf` が正値なら `--spec-min-p` の各 draft 単独の確率による window 判定に代わります。既定値の `0` はこの累積確率判定を無効にし、DFlash2 の window 判定では `--spec-min-p` を使います（`src/program/generate.cpp:795,951,16540-16549`）。

## 使い方

通常の `strata` エンジンで、DFlash2 を明示的に選び、draft モデルと MTP fallback を指定する例です。モデルと pack のパスは手元の環境に合わせてください。

```sh
strata generate --pack ./target.pack --tokens "1,2,3" --spec 4 --mtp ./mtp --draft dflash2 --draft-model ./draft.pack --draft-conf 0.25
```

エンジンの usage は `strata generate --pack DIR --tokens ...` 形式を示しています。`--draft-conf` 自体は `generate.cpp` の共通引数 parser にあり、この usage 形式の起動でも同じ値を受け取ります（`src/program/generate.cpp:944-952,2694-2701`）。

## 値と既定値

- 省略時は `0.0` です。正の値だけが累積積の判定を有効にします。
- `std::clamp` により、負の値は `0.0`、`1.0` を超える値は `1.0` になります。範囲外であることを示す専用エラーはありません（`src/program/generate.cpp:2700`）。
- 数値変換は `std::atof` で、独自の書式・変換失敗検査はありません。同じオプションを複数回指定した場合は、parser が順に代入するため最後の値が残ります（`src/program/generate.cpp:2416-2421,2700`）。
- 値を省略すると `next()` が `--draft-conf needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

DFlash2 の draft から得た確率 `dprob` を順に累積乗算し、積が `P` 以上である間だけ window 長 `T` を増やします。積が `P` 未満になった draft の位置で止まるので、確率の個別値ではなく、連続する draft がすべて妥当である確率の積を基準にします。初回 window は後段で `T = 1` に設定されます（`src/program/generate.cpp:16544-16551`）。

この条件は `--draft dflash2` が実際に有効な場合に限り適用されます。DFlash2 は `--mtp`、`--spec 2` 以上、native pack、`--draft-model` を必要とし、`--serve`、`--batch`、複数 GPU / layer split では使えません。GPU build で pack load に失敗した場合も MTP に戻ります。DFlash2 が build に含まれない場合もこの専用分岐はコンパイルされません（`src/program/generate.cpp:5447-5452,5474-5514`; `CMakeLists.txt:334-341`）。

`--draft-conf` が `0` 以下なら、DFlash2 の window 判定は `--spec-min-p` の単独確率判定に戻ります。DFlash2 が fallback されて MTP が draft する場合も、`--draft-conf` はその window 判定に使われず、MTP 側は `--spec-min-p` を使います（`src/program/generate.cpp:16511-16512,16529,16540-16549`）。なお、`--spec` は window の幅の元となり、DFlash2 の初期化ではカード別上限または `--draft-cap` に応じて `o.spec` が小さくなることがあります。その後の window cycle や suffix draft の処理も判定後に実行されるため、`--draft-conf` の計算だけで最終 window が決まるとは限りません（`src/program/generate.cpp:5498-5503,16531-16555`）。

Qwen3.6 family は共通 parser より前に専用 parser へ振り分けられ、専用 parser のオプション一覧に `--draft-conf` はありません。その family の起動にこのオプションを渡す用途は対象外です（`src/program/generate.cpp:2390-2408`; `src/qwen35/q36_engine.cu:3743-3790`）。

## 適用条件と副作用

このオプション自体は閾値を設定するだけで、ファイルの作成やネットワークアクセスを行いません。DFlash2 を使うときは DFlash2 drafter の追加 VRAM 使用があり、初期化・bind・prepare に失敗すると stderr に理由を出して MTP に fallback します（`src/program/generate.cpp:5474-5514,16148-16165`）。

## 出力とエラー

`--draft-conf` の値を clamp したことや、閾値で window が短くなったことを示す専用メッセージは確認できません。DFlash2 が有効なら起動時に drafter 有効化のメッセージ、終了時に DFlash2 の平均 draft 時間・round 数・VRAM 使用量が出ます。利用できない条件や初期化失敗時は MTP へ戻す理由が stderr に表示されます（`src/program/generate.cpp:5474-5514,16149-16165,16831-16834`）。

値の欠落は終了コード `2` です。未知のオプションも `unknown argument` と usage を stderr に出して `2` で終了します（`src/program/generate.cpp:2418-2420,2784-2794`）。

## 根拠

- `src/program/generate.cpp:792-796,949-952` — DFlash2 関連設定、既定値と usage 説明。
- `src/program/generate.cpp:2416-2421,2694-2701` — 値取得、`--draft` の選択肢、`--draft-conf` の変換・範囲補正。
- `src/program/generate.cpp:5447-5514,16148-16165` — DFlash2 の適用条件、カード別 window 上限、MTP fallback。
- `src/program/generate.cpp:16494-16529,16531-16555` — 累積確率・`--spec-min-p` による判定と後続 window 調整。
- `src/program/generate.cpp:16831-16834` — 終了時の DFlash2 統計。
- `src/qwen35/q36_engine.cu:3743-3790` — Qwen3.6 専用 parser が受け付ける引数。
- `CMakeLists.txt:334-341` — DFlash2 実装を CUDA/HIP build に含める条件。

本調査では既存 CLI の help を別途実行しておらず、Release artifact の挙動も確認していません。記述は上記 checkout のソースに基づきます。
