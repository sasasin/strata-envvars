# `STRATA_PIN_RESERVE_GIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。調査対象の作業ツリーは `main`（`origin/main` と同じ HEAD）。

## 役割

この HEAD の Strata 所有ソースでは、`STRATA_PIN_RESERVE_GIB` を環境から読み取る実装を確認できませんでした。そのため、この環境変数が起動時の空き RAM、expert copy の pinning、またはその他の実行動作を変えるとは、現行コードからは結論できません。

## 値と判定

ソースに読み取り処理がないため、未設定、空文字、数値、負値、不正文字列の判定、既定値、範囲制限はいずれも確認できません。変換方法や clamp の有無も確認できません。

## 有効になる条件

Strata 本体、CUDA/HIP/SYCL 実装、Python セットアップ・サーバー、および同梱ツールのソースで、この名前を参照する箇所は見つかりませんでした。したがって、OS、backend、ビルド条件、CLI オプションに応じて有効になる経路も、ソースからは確認できません。

近接する実装では、`--resident-experts` と `--resident-budget-gib` の引数処理時に `STRATA_RESIDENT_HEADROOM_GIB` を読み、値が存在し `std::atof(v) >= 0.0` の場合に RAM headroom を GiB 単位で設定します。これは別の環境変数であり、`STRATA_PIN_RESERVE_GIB` の別名や代替処理であることを示すコードはありません。

## 実行時の詳細

`STRATA_PIN_RESERVE_GIB` の読み取り時期、値のキャッシュ、子プロセスへの転送、ログ・警告・エラーへの影響は確認できません。HEAD 内での完全名検索では `docs/TROUBLESHOOTING.md:120` に「空けておく RAM を設定する」との説明がありますが、これは文書の記述であり、現行ソースの挙動を裏付けません。説明されている default が実際に適用されるかも、ソースからは確認できません。

## 根拠

- `src/program/generate.cpp:2113-2132` — `--resident-experts` と `--resident-budget-gib` の処理。既定 headroom を 4 GiB にし、`STRATA_RESIDENT_HEADROOM_GIB` が設定されていて `std::atof(v) >= 0.0` の場合に値を上書きする。`STRATA_PIN_RESERVE_GIB` の参照はない。
- `src/core/pinned.cu:364-424` — expert arena の CUDA registration と、登録されなかった領域の resident lock 処理。この範囲に `STRATA_PIN_RESERVE_GIB` の参照はない。
- `docs/TROUBLESHOOTING.md:113-120` — `STRATA_PIN_RESERVE_GIB=N` を RAM reserve として説明する文書上の記載。ソース実装の根拠には採用していない。

調査時点の HEAD に含まれる Strata ソースで完全名を検索した限りでは実装を確認できませんでした。このため、このファイルは値の仕様を説明するものではなく、候補一覧にある名前を現行ソースで裏付けられなかったという調査結果です。
