# `STRATA_NO_ARENA_THP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリや Linux kernel の動作は対象外。

## 役割

Linux で expert arena を匿名 mmap した場合に、Strata が `madvise(..., MADV_HUGEPAGE)` を呼んで transparent huge pages (THP) を要求する処理を止めます。THP 自体を無効化する設定ではありません。対象は共有ファイル backing や hugetlb の大ページ割り当てではなく、それらを使わなかった後の匿名 mapping fallback です。

この処理は CUDA/HIP 共通の `src/core/pinned.cu` と SYCL 側の `sycl/src/core/pinned.dp.cpp` にあります。Windows 側の `VirtualAlloc` 分岐にはこの環境変数の読み取りがありません。

## 値と判定

値の内容は parse されず、`std::getenv(...) != nullptr` で設定有無だけを判定します。

| 状態 | `MADV_HUGEPAGE` 要求への影響 |
|---|---|
| unset | THP モードが `always` でなければ要求する。`always` なら要求しない |
| 空文字を含む何らかの値を設定 | THP モードにかかわらず要求しない |
| `0`、`false` などを設定 | 空文字以外と同じく要求しない。値による無効化方法はない |

環境変数の判定に数値変換、大文字小文字変換、空白除去はありません。別変数 `STRATA_NO_LARGEPAGES` が設定されている場合は hugetlb の試行と `MADV_HUGEPAGE` 呼び出しの両方が既に省かれるため、この変数単独の分岐・ログは表に現れません。

## 有効になる条件

- Linux の `reserve()` が共有ファイル mapping を使わず、hugetlb mapping にも成功せず、匿名 mapping fallback まで進むこと。共有ファイル mapping は先に成功して return し、hugetlb mapping も成功時点で return するため、その場合この変数は参照されません。
- `STRATA_NO_LARGEPAGES` が unset であること。この変数が設定済みなら、THP 要求部分の条件も偽になります。
- THP モードが `always` の場合は、変数が unset でも追加の `MADV_HUGEPAGE` を要求しません。Strata は `/sys/kernel/mm/transparent_hugepage/enabled` の先頭行から最初の `[...]` 内を読み、文字列全体が `always` と等しいかを判定します。ファイルを開けない、読み取れない、または括弧がない場合は `always` と判定しません。

setup は、`STRATA_EXPERIMENTAL_GFX1103` が文字列全体で `1`、選択 GPU が `gfx1103`、HIP backend、かつ Windows 以外の場合、実行設定の `env` に `STRATA_NO_ARENA_THP=1` を書き込みます。これは Radeon 780M など gfx1103 の opt-in 経路です。生成された設定の `env` はサーバーが engine 子プロセスの環境へ反映します。直接 engine を起動する場合は、利用者が環境変数を設定したときだけ渡されます。

## 実行時の詳細

判定は arena の `reserve()` 呼び出し中に行われ、static cache されません。予約済みの arena に対する後からの環境変更はその mapping に反映されず、以後に行われる別の予約ではその時点の環境が読まれます。値を設定しても、既に THP がカーネル側で有効である状態を解除する処理や、実際の backing page size を指定する処理はありません。止めるのはこの mapping に対する Strata の `MADV_HUGEPAGE` 要求だけです。

設定された場合、匿名 fallback の arena note に `transparent huge pages skipped (STRATA_NO_ARENA_THP)` を付けます。THP が `always` で変数が未設定の場合は `transparent huge pages are on for every mapping (THP always): MADV_HUGEPAGE not requested`、それ以外で `madvise` が成功すると `transparent huge pages requested (MADV_HUGEPAGE)` を付けます。CUDA engine は `strata generate: expert arena: ...` として note を stderr に出力します。SYCL の generate 経路も同様の形式で出力します。`madvise` が失敗した場合は成功時用の文言を付けません。

setup の gfx1103 opt-in の根拠コメントは、780M の KFD queue が THP による pinned expert arena の移動中に evict される問題への対処としてこの値を設定すると説明しています。`docs/TROUBLESHOOTING.md` も、THP が `always` の場合に余分な要求を避けることと、この変数が設定の違いを問わず要求を省くことを案内しています。これらは資料上の説明であり、この調査では性能や GPU reset の再測定はしていません。

## 根拠

- Linux/Windows 分岐、shared-file mapping の早期 return、hugetlb の試行と fallback: `src/core/pinned.cu:55-68,115-124,189-227`、SYCL 移植版 `sycl/src/core/pinned.dp.cpp:56-72,115-124,190-228`。
- THP モード読取、設定有無の判定、`madvise` と note の生成: `src/core/pinned.cu:228-270`、SYCL 移植版 `sycl/src/core/pinned.dp.cpp:229-271`。
- arena note を stderr に出力: `src/program/generate.cpp:4766-4777`、SYCL `sycl/src/program/generate.cpp:4254-4263`。
- gfx1103 opt-in の値判定と HIP 向け設定: `setup.py:1841-1844,5738-5750`。設定の `env` を engine 子プロセスに反映: `serve/server.py:2622-2638`。
- 関連説明: `docs/TROUBLESHOOTING.md:64-67`。
