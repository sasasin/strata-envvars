# `FNX_SELFTEST_FAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP 版の同梱 split engine が、カード上で実行する kernel self-test の結果を強制的に失敗扱いにする診断用環境変数です。`FNX_SELFTEST=1` などによって self-test を実行する経路で `FNX_SELFTEST_FAIL=1` を指定すると、実際の self-test callback を呼ばずに失敗理由を作り、split engine の初期化を拒否します。通常の計算結果を切り替える設定ではありません。

## 値と判定

`std::getenv` で取得した値を整数変換せず、文字列全体を `strcmp(..., "1")` で比較します。

| `FNX_SELFTEST_FAIL` | 判定 |
|---|---|
| 未設定 | 強制失敗しない。self-test を実行する条件なら通常の callback を呼ぶ |
| `1` | 強制失敗。callback を呼ばず、`forced failure (FNX_SELFTEST_FAIL=1)` を失敗理由にする |
| 空文字、`0`、`01`、`1 `、`true` など | 強制失敗しない。self-test を実行する条件なら通常の callback を呼ぶ |

空白の trim、数値 parse、範囲検査、大文字小文字変換はありません。値がちょうど `1` の場合だけ一致します。強制失敗は self-test の実行条件に従属します。gfx1201 では `FNX_SELFTEST=1` がなければ判定関数が先に戻るため、この変数が `1` でも何も起きません。

## 有効になる条件

- `FNX_HIP` を有効にしてビルドされた split engine であること。`check_cards()` 内の読み取りと判定呼び出しは `#if FNX_HIP` の内側にあり、CUDA 版ではこのコードを通りません。
- モデルを読み込む split engine の初期化で `check_cards()` が呼ばれること。これはモデル内容の検査・ロードより前です。
- 判定に使うのは device 0 の `gcnArchName` です。それが `gfx1201` 以外なら self-test は既定で実行され、`FNX_SELFTEST_FAIL=1` が適用されます。`FNX_SELFTEST` の値はこの既定実行を止めません。
- device 0 が `gfx1201` なら、`FNX_SELFTEST` が文字列全体として `1` の場合にだけ self-test が実行されます。その場合に限り `FNX_SELFTEST_FAIL=1` が適用されます。`FNX_SELFTEST` の未設定、空文字、`01`、`true` などは強制実行になりません。

先にカード数・アーキテクチャ・IOMMU/BAR1 の検査が失敗した場合は self-test 判定に到達しません。CLI 引数や他の環境変数による `FNX_SELFTEST_FAIL` の上書きはありません。相互作用する変数は `FNX_SELFTEST` です。

## 実行時の詳細

`Model` 初期化中の `check_cards()` は、HIP ビルドで device 0 のアーキテクチャ名と `FNX_SELFTEST`、`FNX_SELFTEST_FAIL` の値を取得し、`selftest_decide()` に渡します。`selftest_decide()` は device 0 が gfx1201 かどうかを調べ、gfx1201 かつ `FNX_SELFTEST` が厳密に `1` でない場合は即時 return します。それ以外では全カードについて WMMA、expert tile、dense product、dp4a、recurrent step の self-test callback を実行します。ただし `FNX_SELFTEST_FAIL=1` の場合は callback を呼び出さず、強制失敗にします。

返された各行は `check_cards()` が stderr に `fnx: ` を付けて出力します。強制失敗時は self-test failed の行の後に `std::runtime_error` が投げられ、split engine の初期化が失敗します。gfx1201 で `FNX_SELFTEST=1` も指定した場合は失敗行のみです。未テストのアーキテクチャでは、その前に実験的対応である旨の行も出ます。失敗後に呼び出し元がプロセスを終了するか通常の layer split へ切り替えるかは、この判定箇所ではなく呼び出し元の扱いによります。

観測される失敗行は次の形式です（stderr。`<arch>` はコロンより前のアーキテクチャ名）。

```text
fnx: The split engine's self-test failed on <arch> (forced failure (FNX_SELFTEST_FAIL=1)), so it does not run on this card: the normal layer split starts instead.
```

値は `check_cards()` の実行時に取得され、結果は static cache されません。この判定処理の後にプロセス環境を書き換えても、その初期化での判断は変わりません。後から別の model 初期化で `check_cards()` が実行される場合は、その時点の環境値が再取得されます。

## 根拠

- `src/split/src/model.cpp:100-147` — `check_cards()`、`FNX_HIP` guard、環境値の取得と helper への引き渡し、stderr 出力、失敗時の例外。
- `src/split/src/model.cpp:1253-1266` — `Model` 初期化でカード検査をモデル内容の検査より先に呼ぶ。
- `src/split/src/hip/selftest_policy.hpp:21-50` — gfx1201 判定、`FNX_SELFTEST` の厳密比較、早期 return、`FNX_SELFTEST_FAIL` の厳密比較、callback の省略、成功・失敗行。
- `src/split/src/selftest.cu:306-321` — 通常 callback が各カードで実行する kernel self-test 群。
- `docs/DETAILS.md` には `FNX_SELFTEST_FAIL` の説明は見つからず、この挙動の根拠にはしていない。
