# `STRATA_DF2_WAITCOMMIT`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの動作は対象外。

## 役割

DFlash2 drafter が次の候補を作る前に、直前の verifier commit の完了を待つための測定用切替です。未設定なら DFlash2 の draft と、別 stream 上で進行中の非同期 commit が重なる場合があります。設定すると `Verifier::wait_commit()` を呼んでから DFlash2 の `draft()` を実行します。環境変数の値そのものは読まず、設定の有無だけを見ます。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 待たない |
| 設定あり | 待つ。空文字列、`0`、`false` を含むすべての値が同じ扱い |

判定は `std::getenv(...) != nullptr` です。文字列比較、数値変換、大文字小文字の判定はありません。判定結果は `draft_next` 内の `static const bool` に保存され、最初に DFlash2 の経路で評価された後はプロセス内で再評価されません。

## 有効になる条件

- `STRATA_HAVE_DFLASH2` が定義されたビルドで、CLI の speculative generation 経路を使うこと。
- DFlash2 が実際に有効であること。起動時の選択には `--draft dflash2`、MTP fallback と `--spec 2` 以上、native pack、draft model pack が必要です。複数 GPU、batch、serve、layer split の経路では DFlash2 の選択が拒否されます。
- 後続の検証処理で tap を利用でき、DFlash2 の bind と prepare が成功して `use_df2` が維持されること。利用できない場合は MTP が使われ、この変数による待機は起きません。
- commit が実際に非同期で保留されていること。初期化では `set_commit_async(!multi_gpu)` が呼ばれ、Verifier は `STRATA_COMMIT_SYNC` が未設定の場合だけ非同期 commit を有効にします。`STRATA_COMMIT_SYNC` が設定されている場合、または commit が保留されていない場合、`wait_commit()` による追加待ちはありません。

## 実行時の詳細

speculative loop は verifier の window を commit した後、次の draft を作ります。DFlash2 経路では `STRATA_DF2_WAITCOMMIT` が設定されていれば `ver.wait_commit(err)` を呼び、その成功後に `df2.draft(...)` を実行します。未設定ならこの明示的な待機を飛ばして DFlash2 の draft を呼びます。

CUDA verifier の非同期 commit は commit graph を stream に投入し、完了 event を記録して戻ります。`wait_commit()` は保留中の event を同期し、複数 stage の verifier がある場合は次の verifier にも待機を伝えます。このCLI経路は単一 GPU 条件のため通常は1つの verifier です。待機に失敗すると draft callback は失敗し、呼び出し元が `strata generate: <エラー>` を stderr に出して終了コード 1 を返します。正常時にこの環境変数専用のログはありません。

この切替は commit と DFlash2 draft の重なりをなくすため、測定時に重なりの影響を除く用途です。コードとコメントから待機の順序は確認できますが、この調査では速度や生成結果の測定はしていません。

## 根拠

- `src/program/generate.cpp:16494-16503` — 環境変数の存在判定、commit 待機、DFlash2 draft 呼び出し。
- `src/program/generate.cpp:4237` — multi-GPU でない場合の非同期 commit 設定。
- `src/program/generate.cpp:5474-5517,16148-16165` — DFlash2 の選択条件と、tap/bind/prepare 失敗時の MTP fallback。
- `src/program/generate.cpp:16668-16699` — window commit 後の draft 呼び出しと失敗処理。
- `src/core/verify.cpp:3379-3380,3416-3429,3441-3452` — `STRATA_COMMIT_SYNC` による非同期 commit の抑止、event の記録と待機。
- `include/strata/core/verify.hpp:254-261` — 非同期 commit と `wait_commit()` の契約。
