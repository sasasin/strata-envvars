# `STRATA_SPILL_OFF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

GPU メモリが足りないときに `generate` が自動で選ぶ、prompt 用バッファの小型化・独立確保と、出力 head を後から pinned host memory に移す処理を抑止します。名前に `OFF` とありますが、値を boolean や数値として解釈するのではなく、環境変数が存在するかだけを見ます。設定すると、値が `1` でなくても、空文字でも、これらの自動退避経路の条件が成立しません。

この変数は GPU メモリ退避全般のマスター設定ではありません。たとえば MTP draft layer をロード前に外す処理（`src/program/generate.cpp:6721-6740`）にはこの変数の判定がなく、native head の初回 GPU allocation 失敗時に host memory を試す処理（`src/core/native_head.cpp:61-84`）も `STRATA_SPILL_OFF` を参照しません。

## 値と判定

| 設定状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `std::getenv(...) == nullptr` | 下記条件がそろえば自動調整・退避を許す |
| 空文字 | 非 null | 3 つの自動経路を抑止 |
| `0`、`1`、その他の文字列 | 非 null | 3 つの自動経路を抑止 |

数値変換、文字列比較、範囲検査、無効値時の fallback はありません。各判定は `generate` の自動 cache sizing 部分で直接 `getenv` し、環境変数の値を static cache しません。GPU が discrete かを調べる `spill_discrete_gpu()` の結果は別途 `static const bool` に保存されます（`src/program/generate.cpp:271-283,7604-7605,7651-7652,7680-7681`）。

## 有効になる条件

環境変数が未設定でも、次の各経路の条件を満たす場合だけ処理されます。明示的な `STRATA_SPILL_OFF` の値は、各条件式の該当経路を止めます。

| 経路 | `STRATA_SPILL_OFF` 以外の主な条件 | 設定時の扱い |
|---|---|---|
| prompt の slot loan を縮めて cache を保つ | `--prefill` の chunk が正、prefill が cache を借りる、prefill auto、cache が必要 slot 数未満、reserve 未指定、単一 GPU で layer split なし、discrete GPU。可能な場合は keep 数を 128 から 16 にし、再計算した cache slot 数を使う | loan 縮小を行わず通常の条件判定を続ける（`src/program/generate.cpp:7600-7618`） |
| prompt path 自前の小さい buffer と小さい cache に切り替える | auto cache、prefill が借用可能かつ auto、reserve 未指定、cache が必要 slot 数未満、単一 GPU で layer split なし、expert profile がある、discrete GPU。1024/512/256-token chunk を試し、少なくとも 1 cache slot が取れると選ぶ | 切り替えず、cache が足りない状態なら後続の不足処理へ進む（`src/program/generate.cpp:7646-7674`） |
| native output head を後から pinned host memory に移す | cache が 0、native head がロード済みでまだ host 上でない、reserve 未指定、単一 GPU で layer split なし、`STRATA_HEAD_HOST_OFF` も未設定、discrete GPU | `to_host()` を試さず、cache が 0 の不足処理へ進む（`src/program/generate.cpp:7676-7704`） |

`spill_discrete_gpu()` は Metal build では常に false です。それ以外では CUDA 互換 API から現在 device の属性を取り、取得失敗時は false、integrated GPU では false、discrete GPU では true になります。そのためこの自動調整は Metal と integrated GPU（APU 等）では実行されません（`src/program/generate.cpp:271-283`; 判定関数: `include/strata/core/spill_gate.hpp:8-14`）。SYCL 実装の `sycl/src/program/generate.cpp` にはこの環境変数名の参照がありません。

## 実行時の詳細

1. cache slot 数の初期計算後、cache が必要数より少ない場合に prompt loan 縮小を検討します。成功すれば stderr に `short of GPU memory: the cache ... the loan keeps ...` を出し、必要 slot 数と cache 数を再計算します（`src/program/generate.cpp:7600-7618`）。
2. 続いて必要 slot 数を満たさない場合、プロファイルに基づき prompt path 独自の buffer を確保できる組合せを探します。見つかれば stderr に `the prompt path keeps its own ... more is read from RAM and the SSD, expect it to be slower` と出し、cache、reserve、prefill chunk を更新します。変数が設定済みならこの fallback は行いません（`src/program/generate.cpp:7646-7674`）。
3. さらに cache が 0 なら、条件付きで native head を pinned host memory に移して cache を再計算します。成功時は stderr に `the output head ... moves to pinned host memory ... decode is slower`、失敗時は `the output head stays in VRAM (...)` と出します。`STRATA_SPILL_OFF` が設定されている場合、この試行自体が省かれます（`src/program/generate.cpp:7676-7704`）。
4. 上記の調整後も cache が 0 の場合は stderr に `no VRAM is left for the expert cache` と、必要 slot 数・不足量・対処案を出します（`src/program/generate.cpp:7705-7725`）。この変数専用の警告や終了処理はありません。自動退避を抑止した結果として起動不能になるかは、後続の初期化経路によります。

CLI との関係では、3 経路とも `--vram-reserve-mib` が明示されると対象外です。2 番目は `--expert-cache auto` に相当する `auto_cache`、prefill auto と profile を要求します。1 番目は prefill auto と cache 借用を要求しますが `auto_cache` 自体は条件式にありません。layer split / 複数 GPU では各経路が対象外です（`src/program/generate.cpp:7604-7605,7651-7652,7680-7681`）。

## 根拠

- 候補名のコード全体検索で見つかった実行コードの読み取りは `src/program/generate.cpp:7605,7652,7681` の 3 箇所です。コメントにも `src/program/generate.cpp:7650` に記載がありますが、実際の判定根拠は各行の `std::getenv` 条件です。
- discrete GPU gate と backend / device 判定: `src/program/generate.cpp:271-283`, `include/strata/core/spill_gate.hpp:8-14`。
- MTP layer の自動除外にこの変数を使わないこと: `src/program/generate.cpp:6721-6740`。
- native head 初回 upload 時の host fallback と、その別設定: `src/core/native_head.cpp:61-84`。
