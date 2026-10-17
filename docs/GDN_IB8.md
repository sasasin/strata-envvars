# `GDN_IB8`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

この変数は Metal の GDN parity テスト `metal/tests/gdn_parity.cpp` が実行するカーネル特殊化を選びます。Strata の Metal エンジン本体からは参照されておらず、通常の推論動作を設定する変数ではありません。候補リストにはありますが、実装箇所はテスト専用です。

## 値と判定

| 状態 | テストで選ばれるカーネル | threadgroup サイズ |
|---|---|---:|
| 未設定 | `gdn_step`（`IB=4`） | 512 |
| 設定あり（空文字を含む任意の値） | `gdn_step8`（`IB=8`） | 1024 |

`std::getenv("GDN_IB8")` の null 判定だけで分岐し、値の内容は parse しません。したがって `GDN_IB8=0` や空文字も設定ありとして扱われます。起動したテストプロセス内で値を読み、同プロセス中の各 parity/bench pipeline 選択に使います。

## 有効になる条件

この設定は Metal の `gdn_parity` テストを実行するときにだけ作用します。変数が設定されると、テストは `gdn_step8` pipeline の最大 thread 数が 1024 以上か確認し、満たさない特殊化があれば `FAIL` を表示して終了コード 1 を返します。未設定なら必要数は 512 です。変数の設定自体でテストが自動実行されたり、製品エンジンの選択が変わったりはしません。

## 実行時の詳細

テストは `disp()` で threadgroup サイズを切り替え、parity と `--bench` の各 pipeline 作成でも同じ設定有無に応じて `gdn_step` / `gdn_step8` を選びます。テストの他の比較・参照計算は共通です。Metal カーネルでは `gdn_step` が `IB=4`、`gdn_step8` が `IB=8` の template specialization として公開され、カーネルコメントはそれぞれ 512 / 1024 thread の起動条件を記しています。

## 根拠

- `metal/tests/gdn_parity.cpp:54-63` — `getenv` の有無による threadgroup サイズ選択。
- `metal/tests/gdn_parity.cpp:65-79` — 選択された pipeline の特殊化ごとの必要 thread 数チェックと失敗時の終了。
- `metal/tests/gdn_parity.cpp:81-100,176-200` — bench と parity の pipeline 選択。
- `metal/kernels/gdn.metal:30-36,169-170` — 512 / 1024 thread 条件と `gdn_step` / `gdn_step8` の特殊化。
- `metal/src/engine/window.cpp:696-708` — Metal エンジン本体は `gdn_step` を起動し、threadgroup サイズを 512 に指定する。`GDN_IB8` による分岐はない。
