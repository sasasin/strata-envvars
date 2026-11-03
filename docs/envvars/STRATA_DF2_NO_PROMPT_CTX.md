# `STRATA_DF2_NO_PROMPT_CTX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソース。候補一覧 `000_envvers.md` に名前がある。

## 役割

SYCL 版の `strata serve --draft dflash2` で、batched prompt prefill が得た tap rows を DFlash2 drafter の context に追加しないための測定用フックです。prompt の読み込み自体や verifier の処理を止める変数ではありません。通常の `strata generate` 経路にはこの変数の読み取りがありません。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` だけで設定有無を判定します。

| 環境状態 | 判定 | batched prompt の tap callback |
|---|---|---|
| 未設定 | `skip == false` | `df2.context(taps, rows, pos0, e)` を呼ぶ |
| 設定あり | `skip == true` | `true` を返して正常扱いにし、`df2.context(...)` を呼ばない |

したがって `1` だけでなく `0`、`false`、空文字を含む任意の設定値で抑止します。数値変換、境界値、無効値時の fallback はありません。CLI 引数や別の環境変数による上書きも、この判定箇所にはありません。

判定は callback 内の `static const bool` で初回実行時に一度行われ、その値をプロセス内で再利用します。初回評価後にプロセス環境を変更しても再評価されません。DFlash2 を使わず callback が設定・実行されない場合、この値は読み取られません。

## 有効になる条件

- SYCL 実装の `sycl/src/program/generate.cpp` で、`use_df2` が真のサーバー経路に限ります。同箇所で `--draft dflash2` の bind / prepare と tap 確保が行われてから callback が設定されます。
- 抑止されるのは `sp.on_taps` callback を通る batched prompt prefill です。prompt の各区間は `windows_ok` の結果で verify-window 読み込みか batched 読み込みに分けられ、後者が `sp.run(...)` を呼びます。verify-window 経路は `df2.context(...)` を直接呼ぶため、この変数の抑止対象ではありません。
- `strata generate` の prompt path は別 callback を使い、環境変数を参照しません。
- `STRATA_DF2_TIMING` は別の計時用設定であり、この変数の有効条件や値判定を変えません。

## 実行時の詳細

通常の batched prompt path では `Prefill::run` が tap rows の準備後に `on_taps` を呼びます。環境変数が設定されていると callback は成功 (`true`) を返すだけで、DFlash2 の `context` 更新をスキップします。その結果、prompt の tap rows は drafter に渡されず、prompt 全体の文脈を使えないため初期の DFlash2 draft の質が下がり得ます。これは測定用の経路であり、ここでは性能・生成結果への定量的な影響を示す資料は確認できません。

対象外の経路では更新が続きます。verify-window prompt read は commit 後に `df2.context(...)` を直接実行します。また request 終了時には、生成した window rows を `df2.context(...)` に渡す処理があります。したがって、設定時も DFlash2 context が全面的に無効になるわけではありません。

callback 内で `skip` が偽のときの `df2.context(...)` が失敗すると callback は `false` を返し、`Prefill::run` も失敗します。サーバーの prompt 読み込み側は stderr に `strata serve: <理由>`、stdout に `ERR <理由>` を出して要求処理を終了します。`skip` が真のときは callback 自体が成功を返すため、この prompt-context 更新に由来する失敗経路には入りません。環境変数の判定自体によるログや警告はありません。

## 根拠

- `sycl/src/program/generate.cpp:7674-7685` — サーバーの DFlash2 初期化条件と tap / VRAM 準備失敗時の起動拒否。
- `sycl/src/program/generate.cpp:7687-7699` — コメント上の測定用途、設定有無判定、cache、batched prompt callback と有効ログ。
- `sycl/src/prefill/prefill.cpp:4994-4997` — tap rows がある場合に `on_taps` を呼び、false を失敗として返す処理。
- `sycl/src/program/generate.cpp:10644-10659,11132-11150` — prompt 区間を verify windows / batched path に振り分ける条件。
- `sycl/src/program/generate.cpp:10786-10830` — verify-window prompt path が `df2.context(...)` を直接呼ぶ処理。
- `sycl/src/program/generate.cpp:10836-10841,11153-11170` — batched prompt の完了と prompt 読み込み失敗の stderr / `ERR` 出力。
- `sycl/src/program/generate.cpp:12255-12264` — request 終了時の DFlash2 context 更新。
- `sycl/src/program/generate.cpp:12712-12715` — `strata generate` の別 callback。対象変数の判定はない。
